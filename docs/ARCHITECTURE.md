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
- `app/db`: shared metadata, synchronous sessions, domain models, and readiness
- `app/health`: liveness and readiness endpoints

The confirmed data model uses one SQLAlchemy persistence model per file under a
shared `app.db.models` package and metadata object. Product modules, routers, and
use cases are introduced only when confirmed behavior reveals useful boundaries.

Detailed rules for introducing those boundaries are indexed in
[`docs/development/README.md`](development/README.md). They adapt Clean Architecture
and domain-modeling practices to this synchronous FastAPI modular monolith without
requiring speculative layers.

## HTTP contract

Product routes belong under `/api/v1`. `/health` confirms that the process can serve requests. `/ready` executes `SELECT 1` and returns 503 when PostgreSQL is unavailable. Both are unauthenticated operational endpoints.

Failures use RFC 9457 `application/problem+json` with `type`, `title`, HTTP `status`, safe `detail`, request `instance`, stable English `code`, and `request_id`. Validation may include field errors. The contract never includes raw input or private exception messages.

## Data access

SQLAlchemy 2 uses one shared declarative base and synchronous session lifecycle through Psycopg 3. Alembic owns schema evolution. PostgreSQL-native enums, UUID arrays, JSONB, checks, deferrable foreign keys, and deletion behavior are defined consistently in the models and initial migration.

The local/test-only seed uses deterministic UUIDs and one transaction. It is idempotent and non-destructive, contains only synthetic identities and `.invalid` URLs, and stores passwords with the same shared Argon2id service used by product code.

SQLite is not a supported substitute. Unit tests isolate technical probes where useful; CI exercises readiness and migrations against PostgreSQL 18.4.

## Request logging

The application emits one key-value completion event per non-health HTTP request. It contains a UTC timestamp, level, route template, method, status, duration, and request ID. It deliberately omits bodies, query strings, headers, credentials, and personal data. This offers grep-friendly MVP diagnostics without adding an observability vendor.

## Deferred capabilities

Authentication, RBAC, audit persistence/retention, certificate or file storage, background work, caching, deployment platform, and external observability are not bootstrap assumptions. Each requires confirmed product or operational requirements before implementation.
