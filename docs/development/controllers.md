# FastAPI routers

A route handler translates HTTP to an application input, calls one operation, and
translates the result to a response DTO.

## Rules

1. Declare method, path, response model, success status, and documented error
   responses.
2. Receive validated values through FastAPI parameters and Pydantic schemas.
3. Inject sessions and replaceable clients with FastAPI dependencies.
4. Call one application service/use case per handler.
5. Do not query SQLAlchemy directly when a business operation exists.
6. Do not implement checksum, eligibility, conflict, or provider rules in routes.
7. Do not catch exceptions merely to rebuild an error response; global handlers
   own RFC 9457 translation.
8. Never return provider payloads, ORM instances, passwords, or hashes.
9. Keep handlers stateless and avoid logging request values or bodies.
10. Register product routers under `/api/v1`.

If a handler needs two application operations, introduce one operation that owns
the orchestration rather than coordinating them in HTTP code.
