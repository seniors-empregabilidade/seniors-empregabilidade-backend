# Testing rules

Tests mirror the production module and focus on observable behavior or meaningful
invariants.

```text
app/db/models/company.py
tests/db/models/test_company.py

app/companies/domain/cnpj.py
tests/companies/domain/test_cnpj.py
```

## Rules

- Organize tests by capability, layer, and principal production unit.
- Use one focused test for one behavior; name the expected outcome.
- Cover success, boundary, and typed failure paths.
- Test value objects and policies without FastAPI or a database.
- Test routers through `TestClient` and assert status, media type, and owned DTO.
- Use controlled fakes for external APIs; never call BrasilAPI in the test suite.
- Use real PostgreSQL for migrations, constraints, transactions, arrays, JSONB,
  concurrency-sensitive uniqueness, and rollback behavior.
- Keep fixtures synthetic, explicit, and free of real personal information.
- Verify that failures leave no partial records.
- Do not mock the behavior under test or weaken the 80% coverage gate.

Every schema migration requires `upgrade -> downgrade -> upgrade` against a clean
PostgreSQL database and manual inspection of both directions.
