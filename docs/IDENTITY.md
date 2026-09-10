# Identity integration

The backend sends credentials to Cognito and stores the returned subject in
`app_user.identity_subject`. The local UUID, role, account status, and company
approval remain in PostgreSQL. A subject is an opaque string: never derive it
from an email, rename it to a provider-specific field, or assume it is a UUID.

## Where to work

| Change | Start here |
| --- | --- |
| Provider operations and safe failures | `app/identity/provider.py`, `exceptions.py` |
| Cognito requests and JWT verification | `app/identity/integrations/cognito.py` |
| Configuring the adapter | `app/identity/dependencies.py`, `app/core/config.py` |
| Login and local account lookup | `app/auth/services/login.py`, `current_user.py` |
| Protecting an endpoint | `app/auth/dependencies.py` |
| Confirming email | `app/accounts/services/confirm_email.py` |
| Company registration and rollback | `app/companies/services/register_company.py` |
| Schema and synthetic data | `alembic/versions`, `scripts/seed.py` |
| Proposed AWS configuration | `infra/cognito` |

`IdentityProvider` is a Python protocol: operations call its methods without
knowing which SDK implements them. To add another provider, implement this
protocol and change dependency composition. Do not copy Cognito calls into each
feature. Only the adapter and its configuration use Cognito-specific names.

## Registration, confirmation, and login

```mermaid
sequenceDiagram
    participant UI as Frontend
    participant API as FastAPI
    participant Registry as BrasilAPI
    participant DB as PostgreSQL
    participant ID as Cognito
    UI->>API: POST /api/v1/companies
    API->>API: Validate CNPJ, email, terms, address
    API->>Registry: Get legal name and primary CNAE
    Registry-->>API: Company record
    API->>API: Check blocked CNAE prefixes
    API->>DB: Flush user, address, company; check uniqueness
    API->>ID: SignUp(email, password)
    ID-->>API: Subject and confirmation state
    API->>DB: Store subject and commit pending company
    API-->>UI: 201 {id, email, status: pending}
    UI->>API: POST /api/v1/email-verification/confirm
    API->>ID: ConfirmSignUp(email, code)
    ID-->>API: Confirmed
    API->>DB: Update company confirmation snapshot, if present
    API-->>UI: 204
    UI->>API: POST /api/v1/auth/login
    API->>ID: InitiateAuth(email, password)
    ID-->>API: Tokens
    API->>API: Verify access token
    API->>DB: Find active local user by subject
    API-->>UI: Tokens, local user_id and user_type
    UI->>API: GET /api/v1/auth/me with Bearer access token
    API->>API: Verify token signature, issuer, client and expiration
    API->>DB: Read current role, account and company status
    API-->>UI: Local user and company status
```

Email delivery happens in Cognito. The API does not generate or store confirmation
codes. Confirmation also works without a local row so that an interrupted signup
can be recovered. `company.corporate_email_confirmed` is a snapshot updated on
confirmation or registration recovery, not the authentication authority. A database
failure after remote confirmation can leave that snapshot stale; inspect the
provider state when reconciling it. Confirmation does not approve a company.

## HTTP contracts for the frontend

Every path below starts with `/api/v1`. Open `/docs` on the running API to inspect
complete request schemas. Responses never contain the submitted password.

| Method and path | Request | Success |
| --- | --- | --- |
| `GET /company-registry-records/{cnpj}` | A valid CNPJ | `200` with normalized CNPJ, legal name, trade name, primary CNAE |
| `POST /companies` | See example below | `201` with `id`, `email`, `status: "pending"` |
| `POST /email-verification/confirm` | `email`, `code` | `204`, no body |
| `POST /email-verification/send` | `email` | `202`, no body, including unknown or already confirmed addresses |
| `POST /auth/login` | `email`, `password` | `200` with `access_token`, `id_token`, nullable `refresh_token`, `expires_in`, `token_type`, `user_id`, `user_type` |
| `GET /auth/me` | `Authorization: Bearer <access_token>` | `200` with `id`, `user_type`, nullable `company_status` |

Synthetic registration body (for local tests with the fake registry; do not send
this example to real services):

```json
{
  "cnpj": "11222333000181",
  "display_name": "Synthetic Company",
  "address": {
    "street": "Synthetic Street", "number": "1", "complement": null,
    "neighborhood": "Test District", "city": "Test City", "state": "RS",
    "zip_code": "90000000"
  },
  "corporate_email": "person@company.example.invalid",
  "password": "SyntheticPass!2026",
  "terms_accepted": true,
  "terms_version": "v1"
}
```

Use the **access token** for API requests. The ID token describes the identity and
is rejected as API authorization. Login and authenticated responses use
`Cache-Control: no-store`. The adapter checks RS256 signature, a fixed issuer,
expiration, issuance time, `token_use=access`, client ID and a nonempty subject.
Signing keys come from that issuer's fixed JWKS address and are cached by PyJWT.
The token's own issuer cannot choose the key URL.

For the current frontend, calls belong in the shared API client and feature hooks
following its feature architecture. Keep passwords and tokens out of TanStack
query keys, persisted query caches, logs, and browser URLs. The current Axios
client does not attach bearer tokens yet. Login, confirmation, and registration
are mutations; `/auth/me` is a query. Clear user-specific cached data when changing
accounts, and invalidate `/auth/me` after an account state change.

This backend returns tokens in JSON and does not set session cookies. Browser
session handling must be completed in the frontend integration. Refresh and logout
endpoints are not implemented here; do not treat the returned refresh token as an
automatic session extension. Require a new login when the access token expires.

## Errors and permissions

Failures use `application/problem+json`, with `code`, `detail`, `request_id` and
optional `errors: {field: [messages]}`. General failures need no `errors` object.
Business validation uses request field names such as `cnpj` or `corporate_email`.
Pydantic validation follows the existing convention with locations such as
`body.address.zip_code`; remove the leading `body.` when mapping to a form field.

| Code | HTTP | Frontend action |
| --- | --- | --- |
| `validation_error`, `invalid_cnpj`, `company_email_domain_blocked`, `company_segment_blocked` | 422 | Show field errors and keep entered nonsecret data |
| `password_policy_violation` | 422 | Show `errors.password` |
| `company_cnpj_conflict`, `company_email_conflict` | 409 | Show the conflicting field |
| `identity_conflict` | 409 | Explain that this identity cannot be linked; do not assume email ownership |
| `identity_confirmation_required` | 409 | Confirm the email; retry registration if it was interrupted, otherwise retry login |
| `invalid_verification_code` | 422 | Show `errors.code`; allow requesting another code |
| `invalid_credentials`, `invalid_access_token` | 401 | Keep login errors generic; request a new login for invalid/expired sessions |
| `account_unavailable` | 403 | Explain that access is unavailable |
| `administrator_required`, `approved_company_required` | 403 | Explain that the operation is restricted |
| `authentication_challenge_required` | 403 | No session was created by this API; an MFA/password-change flow is still needed |
| `too_many_attempts` | 429 | Stop automatic retries and let the user wait |
| `identity_provider_unavailable`, `cnpj_provider_unavailable` | 503 | Keep the form available and offer an explicit retry |
| `cnpj_not_found` | 404 | Show that the registry did not find the CNPJ |

A valid token identifies an account. `get_current_user` also reads its local
status on each request; suspended or blocked users fail immediately. Use
`require_administrator` on administrator operations and `require_approved_company`
on company operations that require approval. These guards are available and
tested; future product routes must explicitly use them. Registration, email
confirmation, login, `/health`, and `/ready` remain public. `/auth/me` accepts
pending companies so the UI can explain their status. There is no public endpoint
that creates an administrator or changes roles.

Offline signature validation does not detect a Cognito token revocation until the
token expires. Disabling a local account is checked on every protected request.
Do not promise immediate session revocation solely from provider logout.

## Failures across Cognito and PostgreSQL

The local rows share one transaction. Uniqueness is flushed before signup, so two
requests for the same CNPJ cannot both complete local registration. If persistence
fails after Cognito signup, the provider identity remains available for a retry.
The API does not automatically delete provider users or need IAM administration
permissions. Keeping the identity also avoids deleting a user that a concurrent
retry may have just linked successfully.

A timeout is ambiguous. Cognito may have created the user even when no successful
response arrived. A lost database commit acknowledgement can also mean the local
registration committed. `identity_registration_incomplete` is a safe log event
when the provider returned an identity but local persistence did not finish normally.

For recovery, try login first. If the local registration exists, `/auth/me` returns
its status. Otherwise, confirm the email if needed and submit registration again.
An existing provider identity is reused only after successful password login and
access-token verification. Operators should inspect both systems before any manual
cleanup; never delete an identity using an email match alone. There is no automatic
orphan cleanup job in this PR.

## Running and verifying

From the backend root, follow the existing README to install Python/uv, copy
`.env.example` and start a **local** PostgreSQL. Run:

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --no-access-log
```

Set `COGNITO_REGION=us-east-2`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, and the
backend-only `COGNITO_CLIENT_SECRET` for the chosen client. See
[the AWS configuration steps](../infra/cognito/README.md). Missing pool/client
configuration returns `503` on identity operations; `/health` remains independent
and `/ready` probes only PostgreSQL. A passing `/ready` does not test Cognito.
BrasilAPI needs outbound HTTPS. `BLOCKED_CNAE_PREFIXES` defaults to an empty list;
the team must supply the actual blocked segments rather than inventing a list.

Automated checks use fake identities, botocore `Stubber`, real RSA signatures and
PostgreSQL. They neither create AWS resources nor send email:

```bash
uv run python scripts/validate.py
# With DATABASE_URL pointing to your migrated, disposable local test database:
RUN_DATABASE_INTEGRATION_TESTS=1 uv run python scripts/validate.py
```

For the live smoke test, use an authorized test company and a mailbox controlled
by a tester. Register, receive and confirm the code, log in, then call `/auth/me`
with the access token. Expect `company_status: "pending"`. Try an ID token and an
expired access token and expect `401`. Never put real passwords or tokens in
committed fixtures, shell history, screenshots, or PR comments. Real AWS delivery
and deployment-role permissions remain to be checked after provisioning.

Migration `d21b63ce9810` adds the unique nullable subject and drops `password_hash`.
The initial migration is preserved. Seed users have no subject or password and
cannot log in. Upgrade/downgrade/upgrade can be tested on an empty disposable
database. Downgrade refuses a nonempty `app_user` table because it cannot recreate
credentials; there is no data-preserving rollback to local passwords.

## Remaining work for US-14 and the other teams

This PR supplies company registration and shared identity infrastructure. US-14
still needs administrator approval/rejection, rejection reasons and notifications,
the form integration, and its acceptance tests through the browser. Professional
registration should call the same provider port in its own persistence use case.
Password reset, session refresh/logout, MFA challenges and administrator onboarding
remain separate work. The AWS configuration files below are proposed settings,
not evidence that a pool was deployed.

## References

- [Cognito signup and confirmation](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/DeveloperGuide/signing-up-users-in-your-app.html)
- [JWT verification](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/DeveloperGuide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html)
- [Token revocation limits](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/DeveloperGuide/token-revocation.html)
- [PyJWT verification and signing keys](https://pyjwt.readthedocs.io/en/stable/usage.html)
