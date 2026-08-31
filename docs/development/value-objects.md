# Value objects

A value object represents a business value whose normalization, validation, or
behavior matters. Examples for this project include a normalized, checksum-valid
CNPJ and a corporate email address.

## Creation rule

Use a value object only when it provides at least one of:

- a real invariant;
- canonical normalization;
- meaningful operations or comparisons;
- a business-specific type that prevents accidental interchange.

Ordinary strings, booleans, dates, and UUIDs remain primitives when a wrapper adds
no protection.

## Rules

- Prefer immutable `@dataclass(frozen=True, slots=True)` values.
- Normalize and validate at construction; invalid instances must not exist.
- Compare by value and never assign independent identity.
- Return a new instance for operations that produce another value.
- Do not import Pydantic, FastAPI, SQLAlchemy, settings, or provider clients.
- Raise a typed domain exception with a stable internal meaning.
- Keep HTTP field validation in Pydantic too; DTO validation protects the boundary,
  while the value object protects domain callers.

Do not create generic `StringValue`, `IntegerValue`, or `RequiredValue` wrappers.
