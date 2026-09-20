# The target is Graviton (t4g), so the image must be arm64:
#   docker build --platform linux/arm64 .
#
# The uv tag is pinned on purpose: pyproject.toml requires
# required-version = "==0.11.33" and the floating tag ships 0.9.30, which makes
# `uv sync --frozen` fail. trixie because 0.11.33 + python3.14 has no bookworm
# variant.
FROM ghcr.io/astral-sh/uv:0.11.33-python3.14-trixie-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies in their own layer: touching code does not reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

FROM python:3.14-slim-trixie

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 10001 seniors
WORKDIR /app

COPY --from=builder --chown=seniors:seniors /app /app

USER seniors
EXPOSE 8000

# python instead of curl: the slim image ships no curl, and adding a package
# only for the healthcheck is dead weight on a 0.5 GiB instance.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# 1 worker: each extra worker costs ~80 MB and the instance has 512 MB.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
