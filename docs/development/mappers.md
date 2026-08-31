# Boundary mappers

A mapper is justified when two boundaries have intentionally different shapes. Do
not create one-to-one pass-through mappers.

## Mapper kinds

- Provider mapper: external payload to an owned integration DTO.
- Persistence mapper: ORM representation to/from a behavior-rich domain object.
- Response mapper: domain/application output to a public response DTO.

## Rules

- Provider payloads are parsed once and never escape the integration adapter.
- Response mapping allowlists fields; it never serializes `__dict__` or ORM rows.
- Persistence mapping handles legacy column names and representation differences.
- Mapping is deterministic and contains no database access or business decisions.
- Nullable values are handled explicitly.
- Sensitive fields are excluded by construction, not deleted after serialization.
- Each mapper has focused tests for transformations and malformed external data.

When the application output already exactly matches a small response DTO, construct
the DTO directly rather than adding a mapper layer.
