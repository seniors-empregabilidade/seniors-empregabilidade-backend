# Seniors – Empregabilidade Backend

FastAPI backend for the Seniors – Empregabilidade project, developed by the AGES team. Source code, API contracts, database identifiers, and technical documentation are written in English.

This repository currently contains a technical foundation only. Domain entities, business modules, authentication, authorization, auditing, and file storage will be introduced only after their requirements are confirmed.

## Technology

- CPython 3.14
- FastAPI and Uvicorn
- PostgreSQL 18.4 in Docker Compose
- SQLAlchemy 2 with the synchronous Psycopg 3 driver
- Alembic migrations
- Pydantic Settings
- uv for Python and dependency management
- pytest, Ruff, mypy, and pre-commit

## Requirements

- uv 0.11.33
- Docker with the Compose plugin
- Ports `5432` and `8000` available locally

Python does not use an official LTS designation. The repository pins the current Python 3.14 release line in `.python-version` and constrains the project to Python 3.14.x.

## Local setup

```bash
uv sync --frozen
cp .env.example .env
docker compose up -d postgres
uv run alembic upgrade head
uv run pre-commit install --install-hooks
uv run uvicorn app.main:app --reload --no-access-log
```

On PowerShell, copy the environment file with:

```powershell
Copy-Item .env.example .env
```

The API is available at `http://localhost:8000`. Useful technical endpoints are:

- `GET /health`: process liveness; does not query PostgreSQL
- `GET /ready`: readiness; runs `SELECT 1` against PostgreSQL
- `GET /docs`: interactive OpenAPI documentation
- `GET /openapi.json`: OpenAPI document

The future product API is reserved under `/api/v1`. No product routes exist yet.

## Commands

| Command                            | Purpose                                        |
| ---------------------------------- | ---------------------------------------------- |
| `docker compose up -d postgres`    | Start local PostgreSQL                         |
| `docker compose stop postgres`     | Stop PostgreSQL without deleting data          |
| `uv run uvicorn app.main:app --reload --no-access-log` | Start the API locally       |
| `uv run ruff format .`             | Format Python files                            |
| `uv run ruff format --check .`     | Check formatting                              |
| `uv run ruff check .`              | Run lint rules                                 |
| `uv run mypy`                      | Run strict type checking                       |
| `uv run pytest`                    | Run tests and the 80% coverage gate            |
| `uv run python scripts/validate.py` | Run all backend quality gates                 |
| `uv run alembic upgrade head`      | Apply all database migrations                  |

To remove the local database and all of its data, run `docker compose down --volumes`. This is destructive and should only be used when the local data is no longer needed.

## Configuration

Pydantic validates configuration from environment variables and an optional uncommitted `.env` file.

| Variable       | Default | Purpose |
| -------------- | ------- | ------- |
| `APP_ENV` | `local` | Runtime environment: `local`, `test`, `staging`, or `production` |
| `DATABASE_URL` | Local Compose database | SQLAlchemy URL using `postgresql+psycopg` |
| `LOG_LEVEL` | `INFO` | Python log level |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list of allowed frontend origins |

Never commit credentials or production configuration. The values in `.env.example` are local-only development credentials.

## Database and migrations

The Compose file owns the local PostgreSQL service and persists PostgreSQL 18 data at `/var/lib/postgresql`, the official image path for version 18 and newer.

`alembic/versions` is intentionally empty. Do not create empty or placeholder revisions. After confirmed models exist, import their shared SQLAlchemy metadata in `alembic/env.py`, generate a revision, inspect every operation, and test both upgrade and downgrade behavior.

## Errors and logging

Errors use RFC 9457 `application/problem+json` with an English stable `code` and a request ID. Unexpected errors return safe details and never echo private implementation messages.

The API writes one compact key-value request event to standard output, with UTC timestamp, method, route template, status, duration, and request ID. Health probes are omitted to reduce noise. Request bodies, query strings, credentials, personal data, résumés, and certificate contents must never be logged.

## Contribution

Read [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md), and [docs/AI_USAGE.md](docs/AI_USAGE.md) before contributing. Architecture context is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and accepted decisions are in [docs/adr](docs/adr).
