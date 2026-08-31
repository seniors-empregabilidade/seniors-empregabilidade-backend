# Backend development rules

These rules adapt proven Clean Architecture and domain-modeling practices to this
FastAPI modular monolith. They are constraints for new product behavior, not a
requirement to create empty layers before a use case needs them.

Read [architecture.md](architecture.md),
[object-calisthenics.md](object-calisthenics.md), and
[testing.md](testing.md) whenever changing product code. Then read only the rules
for the layers touched by the change.

| Rule | Read when |
| --- | --- |
| [architecture.md](architecture.md) | Always; module boundaries and dependencies |
| [entities.md](entities.md) | Adding domain entities or behavior |
| [aggregates.md](aggregates.md) | Enforcing invariants across entities |
| [value-objects.md](value-objects.md) | A value has normalization or invariants |
| [policies-and-services.md](policies-and-services.md) | Locating business rules or orchestration |
| [dtos.md](dtos.md) | Defining Pydantic request/response contracts |
| [use-cases.md](use-cases.md) | Implementing application behavior |
| [controllers.md](controllers.md) | Adding FastAPI routes |
| [repositories.md](repositories.md) | Persistence access needs a meaningful port |
| [mappers.md](mappers.md) | Crossing domain, persistence, or HTTP shapes |
| [exceptions.md](exceptions.md) | Adding a failure contract |
| [dependency-injection.md](dependency-injection.md) | Wiring replaceable dependencies |
| [testing.md](testing.md) | Adding or reviewing tests |
| [new-endpoint.md](new-endpoint.md) | Delivering an endpoint end to end |

All code, contracts, stable error codes, and technical documentation remain in
English. Repository-level `AGENTS.md`, ADRs, and confirmed product scope take
precedence over these guidelines.
