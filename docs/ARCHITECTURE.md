# Architecture

CareerOS is a modular, event-driven system built around one idea: **the agent may search,
analyse, rank, draft and prepare autonomously, but every irreversible external action waits for
the user**. This document describes the moving parts and the decisions behind them.

## System overview

```text
   ┌────────────────┐   ┌────────────────┐
   │  Next.js web   │   │  Expo mobile   │      Firebase Auth (ID tokens)
   └───────┬────────┘   └───────┬────────┘
           └─────── HTTPS / JSON (typed client: packages/api-client) ───────┐
                                                                            ▼
                                                        ┌────────────────────────────┐
   Cloud Scheduler ──(OIDC)──► /internal/scheduler/* ──►│    FastAPI (Cloud Run)     │
                                                        │ auth · API · orchestration │
                                                        └──────┬──────────────┬──────┘
                                        enqueue (same txn)     │              │ read/write
                                                               ▼              ▼
                                                  ┌───────────────────┐  ┌────────────────────┐
                                                  │  agent_tasks      │  │ PostgreSQL+pgvector│
                                                  │  (source of truth)│◄─┤ profile · jobs ·   │
                                                  └───────┬───────────┘  │ matches · evidence │
                                 dispatch: DB poll (local) │              └────────────────────┘
                                 or Pub/Sub push (GCP)     ▼
         ┌──────────────────────────────┬──────────────────────────────┬──────────────────────┐
         ▼                              ▼                              ▼                      ▼
  Discovery worker            Intelligence worker             Resume worker         Browser worker
  (ATS APIs, feeds,           (JD extraction, embeddings,     (evidence selection,  (Playwright portal
   JSON-LD pages)              matching, notifications)        LaTeX → PDF)          adapters)
         │                              │                              │                      │
         └──────────── LLM router (Bedrock Claude · Gemini · local heuristics) ───────────────┘
                                        │                              │
                                   Cloud Storage (resumes, screenshots) · Gmail API (approved sends)
```

All workers run the same Python package (`careeros`) with different entry points; the browser
worker uses a Playwright-enabled image.

## Backend module map (`apps/api/careeros`)

Each domain is a vertical slice (`models.py`, `schemas.py`, `service.py`, `router.py`, ...):

| Module | Responsibility |
| --- | --- |
| `core` | logging, errors, crypto, rate limiting, time, polite HTTP |
| `db` | declarative base, session management, model registry |
| `auth` / `users` | Firebase/dev token verification, user records, per-user settings |
| `profile` | the Career Brain: profile, education, experience, projects, research, publications, skills, achievements, career facts, preferences, reusable answers, verification |
| `evidence` | embedding index of career evidence + retrieval |
| `llm` | provider protocol, Bedrock/Gemini/local providers, router, prompt builder, usage tracking |
| `discovery` | job sources, adapters (Greenhouse, Lever, Ashby, SmartRecruiters, RSS, JSON-LD pages, fixtures), normalisation, deduplication, source health |
| `jobs` | canonical jobs, per-user opportunity state, inbox queries |
| `intelligence` | JD extraction (heuristic + LLM), skills taxonomy |
| `matching` | hard eligibility, requirement coverage, semantic dimensions, explanations |
| `notifications` | notification inbox |
| `resume` | evidence selection, tailoring, LaTeX rendering/compilation, validation, versions |
| `companies` | company records and cached company research |
| `contacts` | public contact discovery, verification, relevance |
| `outreach` / `email` | outreach drafts, validation, approval, sending limits, Gmail/mock providers |
| `applications` / `browser` | application state machine, portal adapters, field mapping, answers |
| `tasks` / `events` | task queue, worker runtime, domain events, activity feed |
| `audit` | append-only audit log of external/user actions |
| `storage` | local filesystem / GCS object storage |

## Data flow

1. **Discovery.** Cloud Scheduler calls `/internal/scheduler/discovery`; due sources become
   `RUN_DISCOVERY` tasks. Adapters fetch listings (official APIs first), which are normalised into
   `RawJob → Job` and deduplicated (external id → canonical URL → company/title/location key +
   description hash → near-duplicate text → embedding similarity). Each source run records health.
2. **Understanding.** New jobs get an `ANALYZE_JOB` task: structured JD extraction (cached per
   description hash, shared across users) and a job embedding.
3. **Matching.** `MATCH_JOB` runs per user: hard eligibility checks → requirement coverage against
   the verified profile → vector retrieval of relevant evidence → semantic dimension scores →
   explanation (strengths, gaps, concerns) citing evidence ids. Scores are relevance, never
   "hiring probability". See [MATCHING.md](MATCHING.md).
4. **Notify.** High matches, deadlines, ready resumes, outreach approvals, replies, ... become
   notifications in the inbox (web + mobile).
5. **Prepare.** Resume generation, company research, contact discovery and outreach drafting run
   as tasks on request (or on recommendation) and always produce reviewable artefacts.
6. **Act (with approval).** Sending an email or submitting an application requires an explicit
   user action on a specific, validated artefact. Everything is audit-logged.
7. **Track.** Domain events form per-entity timelines and the agent activity feed.

## Tasks and events

- `agent_tasks` is the **source of truth** for background work. Tasks are inserted in the same
  database transaction as the change that caused them (transactional enqueue), so work is never
  lost or duplicated by a crash between "commit" and "publish".
- Dispatch is pluggable: locally a worker polls with `SELECT … FOR UPDATE SKIP LOCKED`; on GCP a
  Pub/Sub message carrying only the task id is pushed to the worker service, which claims the row.
- Tasks are idempotent (idempotency keys for de-duplication), leased while running (stale leases
  are recovered), retried with exponential backoff + jitter for retryable errors, and move to
  `WAITING_FOR_USER` when a human must act (CAPTCHA, login, sensitive question).
- `domain_events` records typed events (`JOB_DISCOVERED`, `JOB_MATCHED`, `OUTREACH_SENT`, ...).
  The `CareerOrchestrator` maps events to follow-up tasks and notifications; the same table feeds
  timelines and the activity page.

## AI layer

- `LLMProvider` protocol: `generate`, `structured_generate`, `embed`. Implementations:
  `BedrockClaudeProvider` (Converse API, tool-schema structured output, Titan embeddings),
  `GeminiProvider` (google-genai, API key or Vertex AI), and `LocalProvider` (deterministic
  heuristics + hashing embedder, zero cost).
- `LLMRouter` picks provider/model per task from configuration (`LLM_<TASK>_PROVIDER`,
  `<PROVIDER>_MODEL_<TASK>`); every call is metered in `llm_usage`.
- Cost control: deterministic filters first, cached extraction/embeddings/matches/research,
  focused context from vector retrieval, expensive reasoning only when needed.
- Prompt-injection defence: prompts separate SYSTEM / USER PROFILE / TRUSTED INTERNAL / UNTRUSTED
  sections; untrusted text is fenced in tagged blocks whose delimiters are neutralised inside the
  content; outputs are schema-validated and evidence references are checked against what was
  actually provided.
- Grounding validators (resume, outreach, answers) reject numbers, skills or relationships that
  the cited evidence does not support.

## Key decisions

| Decision | Rationale |
| --- | --- |
| Postgres-backed task queue (+ Pub/Sub push) instead of Redis/Celery | Transactional enqueue, one fewer stateful system, `SKIP LOCKED` is plenty for this workload. Rate limiting/caching sit behind interfaces so Redis can be added if the API scales out. |
| Cloud Run instead of Kubernetes | Scale-to-zero, no cluster operations, far lower baseline cost for a personal agent. Images are standard OCI and portable to GKE later. |
| Jobs are global, opportunity state is per user | Public postings and their JD extraction are shared (cheaper, deduplicated); matches, saves, dismissals and applications are private per user. |
| One professional profile per user (MVP) | Everything references `profile_id`, so multiple career tracks can be added later without schema churn. |
| Enums stored as strings | Adding states never needs a Postgres enum migration; values are validated in Python. |
| 1024-dimension embeddings | Supported natively by Gemini (`output_dimensionality`), Titan v2 and the local embedder; every embedding stores the model that produced it. |
| asyncpg driver | Fully async stack; works with the default Windows event loop for local development. |
| Python-first browser automation | Playwright for Python shares models, validation and grounding with the rest of the backend. |

## Deviations from the suggested repository layout

- `packages/shared-types` is realised as `packages/api-client`: types are **generated** from the
  API's OpenAPI schema and shipped together with a typed client used by both web and mobile.
- Prompts live next to the code that uses them (`careeros/llm/prompts`) so they are versioned,
  tested and packaged with the backend.
- Browser automation lives in `careeros/browser` (Python package) with HTML fixtures in
  `fixtures/forms`; resume templates ship inside `careeros/resume/templates`. Generated resumes go
  to object storage, not the repository.
