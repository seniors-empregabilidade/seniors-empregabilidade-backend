# Domain entities

A domain entity has identity and behavior that remains meaningful across state
changes. A SQLAlchemy model is a persistence model and is not automatically a
domain entity.

Create a separate domain entity only when behavior or invariants justify it. Simple
CRUD data may remain represented by validated DTOs and persistence models.

## Rules

- Construction or a named factory must reject invalid state.
- Keep state private or read-only; expose intention-revealing methods instead of
  public mutation.
- Methods enforce their own invariants and return a consistent result.
- Entity equality is based on identity, not every stored attribute.
- Domain entities do not serialize themselves for HTTP or persistence.
- Domain entities do not import frameworks, settings, sessions, or clients.
- Use immutable value objects for values with their own invariants.
- Raise typed domain exceptions; never raise HTTP exceptions in domain code.

Avoid anemic entities that only mirror database columns, universal base classes,
and domain objects introduced solely to satisfy a folder template.
