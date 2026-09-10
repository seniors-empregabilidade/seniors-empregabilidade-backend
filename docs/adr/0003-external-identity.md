# 0003: External identity with a Cognito adapter

Status: Proposed for team review

## Context

The POC needs shared authentication for candidates, companies, and administrators.
The confirmed direction is to let Cognito manage credentials. There are no
production accounts requiring compatibility with local password authentication.
Company registration already has a separate implementation under review; its
validation and persistence flow provide the first consumer of this integration.

## Decision

Application operations depend on `app.identity.provider.IdentityProvider`.
`app.identity.integrations.cognito` implements that port. FastAPI dependencies
select the configured adapter. Business modules do not import boto3 or decode JWTs.

`app_user.id` remains the application UUID. `identity_subject` stores the opaque
identifier returned by the configured provider and has a unique constraint.
One issuer and app client are configured per environment. Supporting several
issuers at once would require uniqueness by issuer and subject; changing the
configured pool alone does not migrate identities.

Cognito owns passwords, confirmation codes, and token issuance. PostgreSQL owns
account status, roles, and company approval. Login does not infer permissions from
an email, request field, or Cognito group. Restricted operations must use the
appropriate dependency from `app.auth.dependencies`.

A new migration removes `password_hash`; the merged initial migration remains
unchanged. Synthetic seed users have a null subject and cannot authenticate.
There is no local-password fallback and no automatic backfill by email.

## Boundaries and tradeoffs

The first implementation keeps the JSON token contract used by the login branch
and accepts a bearer access token. Browser session storage, refresh, logout,
password recovery, and the full company approval workflow need their own endpoint
and frontend integration work. The current frontend main has no auth screens.

Registration flushes local uniqueness constraints before calling the provider.
After a SQL failure, the provider identity remains available for recovery. A retry
can reuse a confirmed identity after password authentication and token verification. An email match
alone never authorizes linking. This is not a distributed transaction;
a timeout can leave an identity requiring confirmation and a registration retry.

Cognito configuration is prepared as AWS CLI input files under `infra/cognito`.
It is not deployed by importing or starting the application. The POC uses the
approved Ohio region, email sign-in and codes, and a confidential backend client.
MFA challenges fail explicitly until a challenge flow is implemented.

See [Identity integration](../IDENTITY.md) for contracts, verification, and the
remaining steps for the team.
