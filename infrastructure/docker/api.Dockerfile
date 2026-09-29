# CareerOS API + worker image (the same image runs both; the command differs).
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Tectonic (self-contained LaTeX engine) for resume PDFs. The musl build is fully static.
ARG TECTONIC_VERSION=0.15.0
RUN curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin tectonic \
    && tectonic --version

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

WORKDIR /app/apps/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/api/ ./
COPY fixtures/ /app/fixtures/
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data/storage /home/app/.cache \
    && chown -R app:app /app /data /home/app
USER app

ENV PATH="/app/apps/api/.venv/bin:${PATH}" \
    LOCAL_STORAGE_DIR=/data/storage

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "careeros.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
