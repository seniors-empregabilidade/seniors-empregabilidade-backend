# Repositories and persistence access

SQLAlchemy and the shared synchronous `Session` are the persistence mechanism. Do
not add a repository class for every table by default.

## Introduce a repository port when

- the domain works with an aggregate rather than rows;
- multiple use cases share non-trivial persistence behavior;
- more than one implementation is expected;
- a port materially isolates a domain/application contract from SQLAlchemy.

Otherwise, an application service may issue focused SQLAlchemy 2 statements using
the injected shared session.

## Rules

- Ports use domain/application language and never expose SQLAlchemy query objects.
- Implementations do persistence only; they do not apply business eligibility.
- Never commit inside a repository. The application transaction owner commits.
- Avoid N+1 access and select only data the operation needs.
- Convert absent rows to `None` only when absence is part of the port contract.
- Let uniqueness constraints remain authoritative under concurrency.
- Map expected integrity conflicts to stable application failures after rollback.
- Use PostgreSQL in integration tests; SQLite is unsupported.
- Never create a second engine, metadata object, or session abstraction.
