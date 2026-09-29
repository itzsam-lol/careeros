# CareerOS API

FastAPI service, background workers and AI agents for CareerOS.

```bash
uv sync                                  # install dependencies (incl. dev group)
uv run alembic upgrade head              # apply migrations
uv run uvicorn careeros.main:create_app --factory --reload
uv run python -m careeros.workers        # task worker
uv run pytest                            # tests
```

See [`docs/DEVELOPMENT.md`](../../docs/DEVELOPMENT.md) for the full local workflow.
