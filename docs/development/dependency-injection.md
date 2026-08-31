# Dependency injection

FastAPI's dependency system and ordinary constructor/function parameters are the
composition mechanism. This project does not use a DI container.

## Rules

- Wire dependencies at routers or application composition, never in domain code.
- Inject the shared SQLAlchemy session through `app.db.session.get_session`.
- Define a `typing.Protocol` for an external provider or genuinely replaceable
  dependency.
- Inject configuration from `app.core.config.Settings`; do not read environment
  variables inside modules.
- Keep dependencies request-scoped unless an immutable, thread-safe client can be
  safely shared.
- Controlled fakes implement the same protocol in tests.
- Avoid service-locator globals and runtime reflection.
- Do not add a container library unless an approved ADR demonstrates a concrete
  need that FastAPI dependencies cannot solve.

The composition boundary selects the real implementation. Application and domain
code must not import a concrete BrasilAPI client merely to construct it.
