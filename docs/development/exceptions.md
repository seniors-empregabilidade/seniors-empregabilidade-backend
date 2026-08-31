# Exceptions and Problem Details

Failures use typed domain/application exceptions internally and RFC 9457 responses
at the HTTP boundary.

## Rules

- Domain exceptions describe business failure without HTTP imports.
- Application exceptions may carry a stable lowercase `snake_case` code and safe
  detail needed by the existing problem handler.
- Convert a failure to HTTP in one centralized boundary.
- Never expose raw exception messages, SQL details, provider responses, or input.
- Never return `None` or booleans when the contract requires a distinct failure.
- Preserve the required stable codes and statuses documented by the use case.
- Unexpected exceptions become `internal_error`; log only safe type and request ID.

Do not catch an exception unless translating it, adding safe context, or ensuring a
transaction rollback. Avoid broad catches in domain and application code.
