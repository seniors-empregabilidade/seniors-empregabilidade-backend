# ADR 0002: API operations and quality gates

- Status: Accepted
- Date: 2026-08-13

## Context

The MVP needs enough diagnostics to correlate failures and enough automated feedback to support a mixed-experience team, without adopting an observability platform or complicated hook tooling.

## Decision

Use RFC 9457 problem details, generated or validated request IDs, root liveness, PostgreSQL readiness, explicit CORS, and standard-library key-value logging to standard output. Do not log bodies, query strings, secrets, or personal data. Disable duplicate Uvicorn access logs and omit health probe noise.

Use Ruff for formatting/linting, strict mypy, pytest with line and branch coverage at 80% or higher, and the pre-commit framework for pre-commit, commit-message, and pre-push gates. GitHub Actions repeats checks and runs the PostgreSQL integration test.

## Consequences

Logs remain readable by humans and basic log aggregators, and request IDs connect client errors to API events. Rich traces, metrics, and alerting remain deferred. Local hooks provide early feedback while CI remains authoritative. PostgreSQL integration requires Docker locally or the CI service.
