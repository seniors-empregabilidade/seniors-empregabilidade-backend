# New endpoint workflow

Build an endpoint from the confirmed behavior outward. Create only the layers the
operation needs.

1. Read the task, wiki, repository instructions, ADRs, and a similar endpoint.
2. Identify invariants, transaction boundaries, provider failures, and sensitive
   values before writing HTTP code.
3. Add value objects, entity behavior, or policies for actual business rules.
4. Define explicit Pydantic request and response DTOs.
5. Define protocols for external providers or meaningful persistence ports.
6. Implement the application operation with one transaction and explicit rollback.
7. Implement provider adapters that parse external data into owned DTOs.
8. Add a thin router with documented responses and dependency wiring.
9. Add focused unit, API, and PostgreSQL integration tests in mirrored directories.
10. Review OpenAPI, RFC 9457 codes/statuses, logs, privacy, concurrency, and partial
    writes.
11. Run `git diff --check` and `uv run python scripts/validate.py`.

## Final checklist

- Domain imports no framework or infrastructure.
- Router has no business rule or direct provider/database orchestration.
- External payloads do not cross the adapter boundary.
- Request and response contracts are owned and exclude sensitive fields.
- Expected failures use stable lowercase `snake_case` codes.
- Database writes share one synchronous session and transaction.
- Uniqueness conflicts, including concurrent conflicts, have deterministic results.
- Tests cover invalid local input without calling the provider and verify rollback.
- No empty architecture layers or speculative abstractions were added.
