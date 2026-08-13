# ADR 0001: Backend platform and data access

- Status: Accepted
- Date: 2026-08-13

## Context

The project has four short academic sprints and contributors with different experience levels. The API needs clear boundaries and production-compatible database behavior without distributed-system or asynchronous complexity.

## Decision

Use CPython 3.14 with uv and a committed lockfile. Build one FastAPI modular monolith. Use PostgreSQL 18.4, synchronous SQLAlchemy 2, Psycopg 3, Pydantic Settings, and Alembic. Run only PostgreSQL in local Docker Compose; run the API directly with uv. Reserve `/api/v1` for product routes.

Do not create domain modules or data models until the scope confirms their entities and responsibilities.

## Consequences

The runtime and local setup remain conventional and explainable. Synchronous request/database code avoids an unnecessary second concurrency model. PostgreSQL behavior is consistent between development and CI. The initial migration history is empty, and the team must add one shared metadata object when the first real model is implemented.
