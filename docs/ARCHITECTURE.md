# Backend architecture

## Runtime shape

The application is a synchronous FastAPI modular monolith:

```text
React SPA → FastAPI /api/v1 → SQLAlchemy → Psycopg → PostgreSQL
```

One deployable API process owns the confirmed product modules. PostgreSQL is the system of record. Local PostgreSQL runs in Docker Compose; the API runs directly through uv for a short feedback loop.

## Current technical boundaries

- `app/main.py`: application composition and middleware registration
- `app/api`: versioned API router composition
- `app/core`: configuration, problem details, logging, and request context
- `app/db`: engine and database readiness infrastructure
- `app/health`: liveness and readiness endpoints

No domain boundary is claimed yet. Models, schemas, routes, repositories, services, and use cases will be introduced only when confirmed entities and behavior reveal useful module boundaries.

## HTTP contract

Product routes belong under `/api/v1`. `/health` confirms that the process can serve requests. `/ready` executes `SELECT 1` and returns 503 when PostgreSQL is unavailable. Both are unauthenticated operational endpoints.

Failures use RFC 9457 `application/problem+json` with `type`, `title`, HTTP `status`, safe `detail`, request `instance`, stable English `code`, and `request_id`. Validation may include field errors. The contract never includes raw input or private exception messages.

## Data access

SQLAlchemy 2 uses synchronous sessions and Psycopg 3. Alembic owns schema evolution. The migration directory is empty because no schema has been confirmed. A shared declarative base and session lifecycle will be added with the first real model rather than as unused abstractions.

SQLite is not a supported substitute. Unit tests isolate technical probes where useful; CI exercises readiness and migrations against PostgreSQL 18.4.

## Request logging

The application emits one key-value completion event per non-health HTTP request. It contains a UTC timestamp, level, route template, method, status, duration, and request ID. It deliberately omits bodies, query strings, headers, credentials, and personal data. This offers grep-friendly MVP diagnostics without adding an observability vendor.

## Deferred capabilities

Authentication, RBAC, audit persistence/retention, certificate or file storage, background work, caching, deployment platform, and external observability are not bootstrap assumptions. Each requires confirmed product or operational requirements before implementation.
