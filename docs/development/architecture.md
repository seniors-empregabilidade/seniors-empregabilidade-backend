# Architecture and dependency rules

## Runtime shape

This backend is one synchronous FastAPI modular monolith. A product module owns a
cohesive capability; it is not a separately deployed service and does not own a
separate database.

```text
HTTP/router -> application service/use case -> domain rules
                       |                         ^
                       +-> integrations          |
                       +-> SQLAlchemy persistence+
```

Dependencies point toward business rules. Domain code must not import FastAPI,
Pydantic, SQLAlchemy, Psycopg, settings, routers, or external API clients.
Application code may depend on domain types and explicit ports. Infrastructure
implements those ports and is wired at the HTTP composition boundary.

## Module shape

Create only directories required by confirmed behavior:

```text
app/<capability>/
├── domain/
│   ├── entities/
│   ├── value_objects/
│   ├── policies/
│   └── exceptions.py
├── schemas/
├── services/
├── integrations/
└── router.py
```

Shared SQLAlchemy persistence remains under `app/db`; operational and cross-cutting
infrastructure remains under `app/core`. A module must not import another module's
private implementation. Share a stable public type or call an application service.

## Rules

1. Routers translate HTTP and call one application operation.
2. Business decisions live in entities, value objects, or pure policies.
3. Application services own orchestration and transaction boundaries.
4. Infrastructure never leaks provider payloads or ORM rows into HTTP contracts.
5. Introduce a port only when a dependency is external, replaceable, or materially
   improves deterministic testing.
6. Do not add empty repository, mapper, factory, aggregate, or service layers.
7. One principal class or concept per file; package `__init__.py` files define the
   intended public surface.

## Import review

Reject framework imports from `domain/` and imports from `router.py` or concrete
integrations inside domain/application rules. Circular imports indicate a misplaced
responsibility or an unstable module boundary.
