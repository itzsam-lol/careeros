# Implementation status

Legend: ✅ Complete · 🟡 Partial · ⚪ Not started

_Last updated: 2026-09-30_

## Phase 1 — Foundation

| Feature | Status | Where | Tests | Notes |
| --- | --- | --- | --- | --- |
| Monorepo, docs, env template, task runner | ✅ | `README.md`, `docs/`, `scripts/dev.py` | — | pnpm workspace uses `node-linker=hoisted` for React Native |
| FastAPI app, settings, structured logging, error envelope | ✅ | `careeros/main.py`, `config.py`, `core/`, `api/` | `test_foundation.py` | — |
| Postgres + pgvector, SQLAlchemy 2 async, Alembic (0001–0006) | ✅ | `careeros/db/`, `alembic/` | DB fixtures | — |
| Auth: self-hosted passwords, Firebase, dev | ✅ | `careeros/auth/` | `test_auth_password.py` | Login rate-limited per process |
| Audit log, rate limiting | ✅ | `careeros/audit/`, `core/ratelimit.py` | `test_foundation.py` | In-memory limiter (single worker in prod) |
| Web app (Next.js) | ✅ | `apps/web` | typecheck, lint, vitest | Glass UI |
| Android app (Expo) | ✅ | `apps/mobile` | typecheck | Light, Apple-style UI; see `docs/MOBILE.md` |
| Single-VM deployment (Compose + Caddy HTTPS) | ✅ | `docker-compose.prod.yml`, `infrastructure/vm/`, `scripts/deploy.py` | — | Nightly `pg_dump` backups |

## Phase 2 — Career profile

| Feature | Status | Where | Tests | Notes |
| --- | --- | --- | --- | --- |
| Profile sections + verification model | ✅ | `careeros/profile/` | `test_profile_api.py` | Imported data starts unverified |
| Career facts derivation | ✅ | `profile/facts.py` | `test_profile_api.py` | — |
| Evidence index (pgvector) | ✅ | `careeros/evidence/` | `test_evidence.py` | Local hashing embedder by default |
| Profile import + loader script | ✅ | `profile/importer.py`, `scripts/load_profile.py` | `test_profile_api.py` | — |

## Phase 3–5 — Discovery, intelligence, inbox

| Feature | Status | Where | Tests | Notes |
| --- | --- | --- | --- | --- |
| Greenhouse, Lever, Ashby, SmartRecruiters, RSS, career pages | ✅ | `discovery/adapters/` | `unit/test_adapters.py` | Official public APIs only |
| Workday career sites | ✅ | `discovery/adapters/workday.py` | `unit/test_adapters.py` | Country facet or text search |
| Curated catalogue: 136 boards with India/Australia roles (incl. Optiver, Akuna, Point72, Quantium) | ✅ | `discovery/catalog.json` | `test_discovery.py` | Verified by probing the APIs |
| Per-source country filter | ✅ | `discovery/service.py` | `test_discovery.py` | Applied before the per-run cap |
| Dedup, normalisation, closing missing jobs | ✅ | `discovery/` | `test_discovery.py`, `unit/test_normalize.py` | ~100 countries, ATS country codes, numbered levels (SDE I) |
| JD extraction (heuristic + optional LLM), injection defence | ✅ | `intelligence/` | `unit/test_extraction.py` | — |
| Matching: eligibility, coverage, scoring, explanations | ✅ | `matching/`, [MATCHING.md](MATCHING.md) | `test_matching.py`, `unit/test_match_rules.py` | Scorer `match-v3`: role type, level fit, implied skills |
| Job function from the title (software, data, research, hardware, sales...) | ✅ | `intelligence/functions.py` | `unit/test_match_rules.py` | Roles outside the target functions are scored down |
| Sponsorship-only countries (e.g. Australia) | ✅ | `matching/eligibility.py`, `matching/service.py` | `test_resumes_api.py` | Ineligible roles there are hidden automatically |
| Inbox, dashboard, notifications | ✅ | `jobs/`, `dashboard/`, `notifications/` | `test_matching.py` | — |

## Phase 6 — Resume engine

| Feature | Status | Where | Tests | Notes |
| --- | --- | --- | --- | --- |
| LaTeX document model (exact round-trip) | ✅ | `resumes/document.py` | `unit/test_resume_engine.py` | — |
| Tailoring: reorder, project swap, verified skills, page fit | ✅ | `resumes/tailor.py` | `unit/test_resume_engine.py` | Deterministic, explainable change log |
| Grounded LLM rephrasing with validator | ✅ | `resumes/tailor.py` | `unit/test_resume_engine.py` | Only runs when an LLM provider is configured |
| Compilation (tectonic/xelatex/lualatex/pdflatex), pdfTeX shim | ✅ | `resumes/latex.py` | `test_resumes_api.py` | — |
| Versions, PDFs, signed download links, notifications | ✅ | `resumes/router.py`, `resumes/service.py` | `test_resumes_api.py` | — |
| Grounded cover letters | ✅ | `resumes/service.py` | `test_resumes_api.py` | — |

## Phase 7–11

| Feature | Status | Notes |
| --- | --- | --- |
| Interview prep (talking points, stories, questions) | ✅ | `resumes/coaching.py` |
| Outreach drafts (referral, LinkedIn note, follow-up, thank-you) | ✅ | Drafts only; the user sends them |
| Application tracking (stages, history, follow-ups, notes) | ✅ | `jobs/router.py`, Tracker tab, web Applications board |
| Company research | ⚪ | — |
| Contact discovery | ⚪ | — |
| Gmail sending with approval | ⚪ | `AUTO_SEND_EMAILS` stays false |
| Application automation (Playwright) | ⚪ | `AUTO_SUBMIT_APPLICATIONS` stays false |
| Push notifications on the phone | ⚪ | Alerts are in-app for now |
