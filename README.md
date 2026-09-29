# CareerOS

**An autonomous personal career agent.** CareerOS keeps a verified, structured model of your
professional background, continuously discovers internships, jobs and research opportunities,
explains which ones fit and why, and prepares the work around them — tailored resumes, grounded
outreach drafts and pre-filled applications — while **you stay in control of every external
action**.

```text
DISCOVER → UNDERSTAND → DEDUPLICATE → MATCH → PRIORITIZE → NOTIFY
        → RESEARCH → TAILOR → APPLY / OUTREACH (with your approval) → TRACK → LEARN
```

## What makes it different

- **Evidence-grounded AI.** Every resume bullet, outreach sentence and application answer is
  traced back to verified facts in your profile ("career facts"). Nothing is invented; unsupported
  claims are rejected by validators, not just discouraged by prompts.
- **Human in the loop by construction.** Applications stop before submission, emails wait for an
  explicit *Send*. `AUTO_SUBMIT_APPLICATIONS` / `AUTO_SEND_EMAILS` cannot be switched on.
- **Untrusted web content stays data.** Job descriptions, web pages and form labels are fenced off
  from instructions in every prompt and never allowed to steer the agent.
- **Respectful automation.** Official ATS APIs and public feeds first, robots.txt and per-host rate
  limits, no CAPTCHA/MFA/login bypassing — the agent hands control back to you instead.
- **Runs free locally.** Deterministic local heuristics and a local embedder mean the whole
  pipeline works without any API keys; plug in Claude (Bedrock) or Gemini per task when you want.

## Apps

| App | Stack | Purpose |
| --- | --- | --- |
| `apps/api` | FastAPI · SQLAlchemy 2 · Alembic · Pydantic 2 | REST API, agents, workers |
| `apps/web` | Next.js · React · Tailwind · shadcn/ui · TanStack Query | Career inbox & full workspace |
| `apps/mobile` | Expo · React Native · TypeScript | Inbox, approvals and notifications on the go |
| `packages/api-client` | openapi-typescript · openapi-fetch | Typed client shared by web and mobile |

Infrastructure: PostgreSQL + pgvector, Cloud Run (API/workers), Pub/Sub, Cloud Scheduler,
Cloud Storage, Secret Manager, Firebase Auth. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, pnpm, Docker.

```bash
python scripts/dev.py setup     # .env, dependencies, Postgres (docker), migrations
python scripts/dev.py dev       # API :8000, worker, web :3000
```

`make setup` / `make dev` work too on systems with make. Open http://localhost:3000 — local
development signs you in as a developer user automatically.

| Task | Command |
| --- | --- |
| Run tests | `python scripts/dev.py test` (`--unit` skips DB/browser/LaTeX tests) |
| Lint / typecheck / format | `python scripts/dev.py lint` · `typecheck` · `format` |
| Migrations | `python scripts/dev.py migrate` · `makemigration "message"` |
| Regenerate API client | `python scripts/dev.py gen-types` |
| Demo data | `python scripts/dev.py seed` |

## Documentation

- [Architecture](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) · [Agents](docs/AGENTS.md)
- [Resume engine](docs/RESUME_ENGINE.md) · [Outreach](docs/OUTREACH.md) · [Portal adapters](docs/PORTAL_ADAPTERS.md)
- [Security](docs/SECURITY.md) · [Deployment](docs/DEPLOYMENT.md) · [Development](docs/DEVELOPMENT.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md) · [Ideas backlog](docs/IDEAS.md)

## Status

CareerOS is under active development. The current state of every subsystem is tracked in
[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).
