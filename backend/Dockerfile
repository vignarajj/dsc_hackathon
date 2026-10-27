# The API image. Build from backend/:  docker build -t dsc-api .
# Run:  docker run -p 8000:8000 -e META_API_KEY=... dsc-api
FROM python:3.14-slim

# uv installs exactly what uv.lock pins.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --system --uid 10001 --no-create-home app
USER app

# Hosts set PORT. FORWARDED_ALLOW_IPS lists the proxies whose X-Forwarded-For
# uvicorn trusts, so the rate limit sees each visitor; see docs/DEPLOY.md.
ENV PORT=8000 \
    FORWARDED_ALLOW_IPS=127.0.0.1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=4)"]

# The process exits at once if META_API_KEY is missing.
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn dsc_backend.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers"]
