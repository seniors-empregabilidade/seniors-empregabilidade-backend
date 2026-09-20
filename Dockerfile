# O alvo é Graviton (t4g), então a imagem precisa ser arm64:
#   docker build --platform linux/arm64 .
#
# A tag do uv é fixa de propósito. pyproject.toml exige
# required-version = "==0.11.33", e a tag flutuante entrega 0.9.30 — com ela
# o `uv sync --frozen` falha. trixie porque a combinação 0.11.33 + python3.14
# não existe em bookworm.
FROM ghcr.io/astral-sh/uv:0.11.33-python3.14-trixie-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependências em camada própria: mexer no código não reinstala tudo.
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

# python em vez de curl: a imagem slim não traz curl, e instalar um pacote só
# para o healthcheck é peso à toa numa instância de 0,5 GiB.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# 1 worker: cada worker extra é ~80 MB, e a instância tem 512 MB.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
