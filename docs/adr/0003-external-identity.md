# 0003: External identity with a Cognito adapter

Status: Proposed for team review

## Context and decision

The POC needs shared authentication across product features. Cognito manages
passwords, confirmation and token issuance. There are no production accounts
requiring compatibility with local password authentication.

Use `app.identity.provider.IdentityProvider` as the application boundary and
`app.identity.integrations.cognito` as its adapter. `app_user.id` remains the local
UUID; the unique `identity_subject` is the opaque identifier returned by the provider.
One issuer and app client are configured per environment. Supporting several issuers
would require uniqueness by issuer and subject.

PostgreSQL remains authoritative for roles, account status and company approval.
Features opt into the existing authentication and permission dependencies. Local
password hashing is removed in a new migration; seed users remain unlinked until
an operator explicitly associates them with synthetic provider identities.

## Scope

This is shared identity infrastructure. Company/professional registration, profile
validation, approval and business notifications belong to their respective PRs.
Feature use cases call the identity port and own their persistence transaction.
An email match does not prove identity ownership. Recovery of an existing identity
requires successful authentication and token verification.

The POC pool and backend client are provisioned in Ohio. The API preserves the
JSON token login contract and existing email-verification paths. Browser session
storage, refresh/logout, password reset and MFA challenge handling are separate
work. See [Identity integration](../IDENTITY.md) for setup and verification.
