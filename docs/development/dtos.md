# DTOs and Pydantic schemas

Pydantic models are HTTP boundary DTOs. They validate transport shape and generate
OpenAPI; they are not SQLAlchemy models or domain entities.

## Organization

Use one principal request or response contract per file when contracts become
substantial. Small contracts used by one endpoint may share a clearly named file.

```text
app/<capability>/schemas/
├── create_company_request.py
├── company_response.py
└── registry_record_response.py
```

## Rules

- Define explicit request and response models; never expose ORM models directly.
- Use strict types, length limits, and field descriptions that match behavior.
- Normalize only transport-level representation at this boundary.
- Convert DTO primitives into domain values before applying business rules.
- Response DTOs contain only the documented public contract.
- Never include passwords, hashes, provider payloads, or internal status details.
- Do not reuse request DTOs as persistence commands when their meanings differ.
- Put cross-field business invariants in domain code, not Pydantic validators.
- Keep examples synthetic and use `.invalid` domains.

FastAPI validation failures and application failures must retain the repository's
RFC 9457 `application/problem+json` contract.
