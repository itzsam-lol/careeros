# Development

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and pnpm 10+
- Docker (for PostgreSQL + pgvector)
- Optional: a LaTeX engine for PDF resumes (`tectonic` recommended — see below)
- Optional: Playwright browsers for application automation (`uv run playwright install chromium`)

## First run

```bash
python scripts/dev.py setup   # copies .env, installs deps, starts Postgres on :5433, migrates
python scripts/dev.py dev     # API http://localhost:8000 (docs at /docs), worker, web :3000
```

Postgres is published on host port **5433** (configurable with `POSTGRES_HOST_PORT`) to avoid
clashing with a locally installed Postgres. The container also creates `careeros_test`.

Local development uses `AUTH_MODE=dev`: the web and mobile apps send `Bearer dev-token` and the
API signs you in as a developer user. Tests use `dev-token:<name>` to create additional isolated
users. Dev auth refuses to start in staging/production.

## Everyday commands

| Command | What it does |
| --- | --- |
| `python scripts/dev.py api` | API only, with reload |
| `python scripts/dev.py worker` | background task worker |
| `python scripts/dev.py test` | backend + frontend tests |
| `python scripts/dev.py test --unit` | fast tests that need no DB/browser/LaTeX |
| `python scripts/dev.py lint` / `typecheck` / `format` | quality gates |
| `python scripts/dev.py makemigration "add x"` | autogenerate an Alembic migration (review it!) |
| `python scripts/dev.py gen-types` | regenerate the typed API client after API changes |
| `python scripts/dev.py seed` | demo profile + fixture job source |

## Backend conventions

- Vertical slices per domain: `models.py` (SQLAlchemy), `schemas.py` (Pydantic), `service.py`
  (business logic, no HTTP), `router.py` (thin FastAPI layer).
- Services never commit. Routers and task handlers commit once per unit of work.
- Every query is scoped by the authenticated user; never accept a `user_id` from clients.
- Tests run against a real Postgres. Each test runs in a rolled-back transaction.
- `mypy --strict` and `ruff` must pass.

## AI providers locally

Everything defaults to `local` (heuristics + hashing embedder). To try real models:

```bash
# Gemini on Vertex AI using your gcloud Application Default Credentials
GEMINI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=<project> LLM_EXTRACTION_PROVIDER=gemini ...
# Claude on Bedrock
AWS_REGION=us-east-1 BEDROCK_MODEL_MATCH=<model or inference profile id> LLM_MATCH_PROVIDER=bedrock
```

## LaTeX

Resume PDFs need a LaTeX engine. `LATEX_ENGINE=auto` tries `tectonic`, `xelatex`, `lualatex`,
then `pdflatex`, including a project-local `.tools/tectonic`. Without an engine the `.tex` source
is still generated and the resume is marked as awaiting compilation.
