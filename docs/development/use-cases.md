# Application services and use cases

An application operation implements one user intention, such as registering a
company. In this codebase it may be a function or class; do not introduce a generic
`UseCase` base class without repeated behavior.

## Rules

- Accept an explicit input DTO or domain values, never `Request` or FastAPI context.
- Orchestrate domain rules, persistence, hashing, and external ports.
- Own one complete transaction boundary for writes.
- Depend on protocols or callables for external providers and other replaceable
  behavior.
- Keep decisions in entities, value objects, or policies; react to their results.
- Return an explicit output value suitable for mapping to a response DTO.
- Raise typed application/domain exceptions with stable codes.
- Never return provider payloads or ORM objects as the public result.
- Never mutate caller-owned input.

Extract shared application services only when two real operations reuse meaningful
orchestration. A long operation may use focused private methods, but excessive
branching usually means a domain policy is missing.
