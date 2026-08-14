# Repository instructions

## Purpose and current scope

This repository is the FastAPI backend for Seniors – Empregabilidade. It currently provides technical configuration only. Do not invent domain entities, database tables, routes, roles, workflows, or file-storage behavior that have not been confirmed by project scope.

The architecture priority is: team knowledge, simplicity and maintainability, mature ecosystem, deployment ease, then sophistication. This is a four-sprint academic project with mixed experience levels.

## Required stack

- CPython 3.14 managed by uv 0.11.33
- FastAPI in a modular monolith
- PostgreSQL 18.4, with local PostgreSQL in Docker Compose
- Synchronous SQLAlchemy 2 and Psycopg 3
- Alembic for schema migrations
- Pydantic and Pydantic Settings
- pytest, Ruff, strict mypy, and pre-commit

Do not replace or duplicate these choices without an approved architectural decision. Do not introduce microservices, Kubernetes, event sourcing, queues, or distributed infrastructure without a confirmed requirement.

## Language

Write code, identifiers, API fields, database identifiers, stable error codes, comments, configuration, tests, branches, commits, pull requests, reviews, logs, and technical documentation in English.

## Commands

Run from the repository root:

- `uv sync --frozen`: reproduce the locked environment
- `uv run uvicorn app.main:app --reload --no-access-log`: local API
- `uv run ruff format .`: apply formatting
- `uv run ruff check .`: lint
- `uv run mypy`: strict type checking
- `uv run pytest`: tests, branch coverage, and the 80% gate
- `uv run python scripts/validate.py`: every backend quality gate
- `uv run alembic upgrade head`: apply migrations

Never bypass pre-commit hooks or reduce quality thresholds to make a change pass.

## Implementation rules

- Keep the application a modular monolith. Add domain modules only after their boundaries and entities are confirmed.
- Keep product endpoints under `/api/v1`; keep liveness and readiness at `/health` and `/ready`.
- Keep route handlers thin when business use cases exist, but do not create empty repository/service/use-case layers now.
- Use synchronous SQLAlchemy and Psycopg. Do not add async database access or a second data-access abstraction.
- Return RFC 9457 `application/problem+json`. Keep stable `code` values in English and never expose exception messages or sensitive data.
- Use `app.core.config.Settings`; do not read environment variables throughout the codebase.
- Do not create placeholder models, schemas, migrations, seeds, routes, authentication, RBAC, audit tables, or storage adapters.
- Add a dependency only when the pull request states the concrete problem it solves.

## Database and migrations

- PostgreSQL is the only supported database. Do not substitute SQLite in tests.
- `alembic/versions` remains empty until a confirmed schema exists.
- After models exist, expose one shared SQLAlchemy metadata object to Alembic.
- Inspect generated migrations. Test upgrade and downgrade behavior against PostgreSQL.
- Never modify an already merged migration.
- Never delete or reset database volumes without explicit authorization and a verified local-only target.

## Logging, privacy, and security

Write compact structured key-value events to standard output. Use the request ID for correlation. Never log request/response bodies, query strings, credentials, tokens, authorization headers, personal data, résumés, certificates, file contents, or database URLs. Prefer route templates over raw paths.

Use synthetic, anonymous test data. Never copy stakeholder or user data into source, fixtures, logs, migrations, documentation, or AI prompts.

Authentication, authorization, audit retention, and file storage are deliberately deferred. Do not imply that the bootstrap protects product data before those requirements are implemented.

## Tests

- Test observable API behavior and failure contracts.
- Keep global line and branch coverage at or above 80%.
- Mark tests that require PostgreSQL with `integration`; CI must run them with PostgreSQL 18.4.
- Avoid mocks for business behavior when real modules exist. Small infrastructure probes may use controlled fakes.
- Do not add factories, Faker, testcontainers, or async test plugins until a real need appears.

## Git and review safety

- Follow Conventional Commits in English.
- Never add a `Co-authored-by` trailer. Preserve the human contributor's configured Git authorship.
- Do not commit, push, open, approve, or merge a pull request unless the user explicitly requests that action.
- Never force-push `main`, push directly to it, or use `--no-verify`.
- Preserve human edits and unrelated working-tree changes.
- Every pull request requires approval after the latest reviewable push from another person in AGES III or AGES IV.

## AI use

Follow `docs/AI_USAGE.md`. Humans own every submitted change, must understand it, and must run the stated validation. Never send secrets or personal data to an AI tool. Disclose material assistance in the pull request template; prompts do not need to be published. AI cannot review or approve its own output.
