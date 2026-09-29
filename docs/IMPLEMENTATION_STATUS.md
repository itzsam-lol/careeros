# Implementation status

Legend: ✅ Complete · 🟡 In progress · 🔴 Blocked · ⚪ Not started

_Last updated: 2026-09-29_

## Phase 1 — Foundation

| Feature | Status | Files | Tests | Known issues | Next step |
| --- | --- | --- | --- | --- | --- |
| Monorepo layout, docs, env template | ✅ | `README.md`, `docs/`, `.env.example` | — | — | — |
| FastAPI app factory, settings, structured logging | ✅ | `careeros/main.py`, `config.py`, `core/` | `tests/test_foundation.py` | — | — |
| Error envelope, security headers, request ids | ✅ | `careeros/api/` | `test_foundation.py` | — | — |
| Postgres + pgvector, SQLAlchemy 2 async, Alembic | ✅ | `careeros/db/`, `alembic/` | DB fixtures | — | — |
| Auth abstraction (Firebase + dev) | ✅ | `careeros/auth/` | `test_foundation.py` | Firebase path needs a real project to exercise end-to-end | — |
| Audit log | ✅ | `careeros/audit/` | `test_foundation.py` | — | — |
| Rate limiting (interface + in-memory) | ✅ | `core/ratelimit.py` | `test_foundation.py` | per-instance only | Redis backend if scaled out |
| Docker Compose, dev task runner, Makefile | ✅ | `docker-compose.yml`, `scripts/dev.py` | — | — | — |
| Next.js web scaffold | ⚪ | `apps/web` | — | — | — |
| Expo mobile scaffold | ⚪ | `apps/mobile` | — | — | — |
| CI (GitHub Actions) | ⚪ | `.github/workflows` | — | — | — |

## Phase 2 — Career profile

| Feature | Status | Files | Tests | Known issues | Next step |
| --- | --- | --- | --- | --- | --- |
| Profile domain + verification model | ⚪ | | | | |
| Career facts derivation | ⚪ | | | | |
| Evidence index (pgvector) | ⚪ | | | | |
| Profile UI | ⚪ | | | | |

## Phase 3+ (planned)

| Phase | Status |
| --- | --- |
| 3 Job discovery (sources, adapters, normalisation, dedup, scheduler, workers) | ⚪ |
| 4 Job intelligence (JD extraction, embeddings, matching, explanations) | ⚪ |
| 5 Career inbox (dashboard, cards, notifications, job detail) | ⚪ |
| 6 Resume engine (LaTeX, grounding, validation, versions) | ⚪ |
| 7 Company research | ⚪ |
| 8 Contact discovery | ⚪ |
| 9 Outreach + Gmail | ⚪ |
| 10 Application automation (Playwright) | ⚪ |
| 11 Tracking & timelines | ⚪ |
| 12 Hardening, deployment, CI/CD | ⚪ |
