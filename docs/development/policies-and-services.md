# Policies and services

Use this decision order to place behavior:

1. A rule about one entity belongs on that entity.
2. A rule about one value belongs in its value object.
3. A stateless calculation across inputs belongs in a pure domain policy.
4. Coordination of persistence, providers, and domain objects belongs in an
   application service/use case.
5. HTTP translation belongs in the router; provider translation belongs in an
   integration adapter.

## Domain policies

- Are pure and deterministic.
- Receive domain values or primitives with clear business meaning.
- Have no session, settings, clock, HTTP, or provider imports.
- Return a decision/value or raise a typed domain exception.
- Receive configuration as an explicit immutable value when it changes the rule.

## Application services

- Coordinate dependencies and transactions.
- Do not become collections of unrelated utility methods.
- Do not hide database commits inside nested helpers.
- Make side-effect order and rollback behavior reviewable.

For US-14, CNPJ validity belongs in a value object, blocked CNAE evaluation in a
policy, and company registration orchestration in an application service.
