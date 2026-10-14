# The smart-able web service: sign in, upload, list, share, and serve
# extracted datasets. Extraction itself runs in the job image (Dockerfile.job).
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra web --no-install-project

# the browser page and the docs page are served from the checkout, so copy
# just what the service reads, and build the docs page (it reads index.html's
# design tokens)
COPY browse/index.html browse/build_quirks.py browse/
COPY docs/smart-data-quirks.md docs/
RUN /app/.venv/bin/python browse/build_quirks.py docs/smart-data-quirks.md browse/quirks.html
COPY web web

ENV PATH="/app/.venv/bin:${PATH}"
WORKDIR /app/web
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'
