# Aggregates

An aggregate is a group of domain entities and value objects that must change in
one consistency boundary. The aggregate root is the only public mutation entry.

Create one only when all conditions hold:

1. An invariant spans more than one entity.
2. The members are loaded and saved together.
3. One transaction must protect the entire change.

## Rules

- Expose one root and keep child mutation behind root behavior.
- Reference another aggregate by identifier, not by embedding its object graph.
- Validate cross-entity invariants on construction and every mutation.
- Do not expose mutable internal collections.
- Persist one aggregate through one meaningful repository port when needed.
- Keep the aggregate free of FastAPI, Pydantic, SQLAlchemy, and client imports.

Foreign-key relationships alone do not make an aggregate. Do not introduce an
aggregate until confirmed behavior requires the consistency boundary.
