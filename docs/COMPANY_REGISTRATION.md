# Company registration and approval (US-14)

Related tasks: [registration](https://app.clickup.com/t/86e309dy1),
[approval](https://app.clickup.com/t/86e309dye),
[integration](https://app.clickup.com/t/86e309dyt), and
[form](https://app.clickup.com/t/86e308wrh).

## Registration

1. `GET /api/v1/company-registry-records/{cnpj}` validates the CNPJ check digits
   before querying BrasilAPI. The response contains the legal name and primary CNAE.
2. `POST /api/v1/companies` validates the submitted company, corporate email,
   address and terms acceptance. Legal name and CNAE are obtained again from the
   registry; the browser cannot override them. LinkedIn is optional and must be an
   HTTPS company profile on `linkedin.com` or `www.linkedin.com`.
3. The service flushes the address, local user and pending company inside one
   transaction. Database uniqueness constraints arbitrate concurrent requests
   before any identity creation. Conflicts map to `errors.cnpj` or
   `errors.corporate_email`, alongside the stable error code.
4. `IdentityProvider.register` creates the Cognito identity or reuses an existing
   identity only after proving ownership through authentication. The backend stores
   its subject in `app_user.identity_subject`. It does not hash or persist passwords.
5. The successful response is `201` with `id`, `email`, `status: "pending"`, and
   `email_confirmation_required`. When confirmation is required, use the existing
   `/api/v1/email-verification/confirm` and `/send` endpoints.

The ClickUp subtask follows the external identity decision in ADR 0003 and merged
PR #15. See [Identity setup](IDENTITY.md) for the shared
Cognito environment and access-token contract.

`company.corporate_email_confirmed` records the identity state observed during
registration. It is not a live copy of Cognito and is not used as an authorization
condition. Cognito controls whether an unconfirmed identity can authenticate.

## Failures and retry

PostgreSQL changes are atomic; AWS and PostgreSQL do not share a transaction.
A provider failure rolls back all local registration rows. If Cognito created an
identity before a timeout or database failure, that identity may remain there.
The API never deletes an identity as compensation: a timeout can also mean the
local commit succeeded but its acknowledgement was lost.

If a code was received and the local account was not saved, confirm the email,
then submit the same registration again with the correct password. The Cognito
adapter verifies ownership before returning an existing subject. An already saved
local account returns a field conflict and should proceed to login. Retrying with
someone else's password cannot attach that person's identity.

The frontend preserves entered values after a failure and offers confirmation
before retry. Confirmation does not approve the company.

## Administrator decision

`PATCH /api/v1/companies/{company_id}/approval` requires a valid access token
belonging to a local administrator. A request is either:

```json
{"status": "approved"}
```

or:

```json
{"status": "rejected", "reason": "Synthetic review reason"}
```

Only a pending company may transition. A row lock serializes simultaneous
administrative decisions; a second decision receives `409 company_not_pending`.
Approval checks the stored primary CNAE against the current blocked prefixes.
Missing activity or a blocked segment prevents approval.

Rejection requires a nonblank reason of at most 2,000 characters. The status and
an in-app `notification` row are committed together. Notification persistence
failure rolls back the decision. This task uses the existing notification table;
no email or push-notification delivery is claimed.

The domain approval policy validates when a reason is required; the HTTP schema
limits its shape and length. Invalid reason/status combinations return
`422 invalid_company_decision` with `errors.reason`.

`GET /api/v1/companies/me` lets the authenticated company read its own status and
rejection reason. It accepts no arbitrary user ID. Pending and rejected companies
can read this result. Other account types receive `403`.

Existing product endpoints must use `require_approved_company` when their
functionality requires an approved business. Approval updates what that dependency
reads from PostgreSQL; it does not grant an administrator role or modify Cognito
claims. Publishing jobs is a separate user story, not an endpoint added here.

## Configuration and open product inputs

- `BRASIL_API_BASE_URL` and `BRASIL_API_TIMEOUT_SECONDS` configure the existing
  synchronous registry adapter. `httpx2` is a runtime dependency.
- `BLOCKED_CNAE_PREFIXES` is a JSON list of CNAE prefixes. The repository default is
  `[]`, meaning no configured segment restriction. **The actual blocked segments
  have not been specified in the inspected tasks or repository.** Supply the agreed
  list for the target environment before accepting the real blocked-segment case.
  Tests use an explicit synthetic policy; they do not establish a product list.
  Each prefix must have one to seven ASCII digits; dots, slashes and hyphens are
  normalized. Invalid entries prevent startup instead of silently weakening the list.
- `PERSONAL_EMAIL_DOMAINS` may extend the database-enforced blocked domain list.
- The frontend currently sends `terms_version: "v1"`. A published legal document
  and its agreed version were not found in the inspected sources. Match the value
  to the approved document before presenting acceptance as legally finalized.
- LinkedIn is requested by the parent task but not marked mandatory. The field is
  optional and does not set `linkedin_verified`.
- The frontend work builds on the candidate registration in frontend PR #19,
  preserving its existing form. Its login link targets `/login`, owned by the
  separate login screen PR. This PR does not implement professional registration
  or replace that login screen.

## Local verification

Run commands from the backend root. Configure `.env` using `.env.example` and
`docs/IDENTITY.md`; keep secrets outside Git. Start only your own local PostgreSQL,
then run:

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --no-access-log
```

Open `/docs` on that local API to inspect request schemas. For automated checks,
set `APP_ENV=test`, `DATABASE_URL` to an isolated PostgreSQL 18.4 database and
`RUN_DATABASE_INTEGRATION_TESTS=1`, then run:

```bash
uv run python scripts/validate.py
```

The tests stub external identity and registry responses. They cover successful
registration, field errors, provider payload limits, uniqueness, rollback of all
local rows, uncertain commits, recovery, login, authorization, rejection reasons,
atomic notification persistence and concurrent decisions. They do not send mail
or call the shared Cognito pool.

For a manual flow with authorized test accounts:

1. Start the frontend with `VITE_API_URL` pointing to the local `/api/v1`.
2. Open `/users/register`, choose Empresa, enter CNPJ and CEP, and wait for lookup.
3. Fill the remaining fields, accept terms and submit once.
4. Confirm the email if requested. The company remains pending after confirmation.
5. Log in; `GET /api/v1/companies/me` reports `pending`.
6. With a different administrator account, approve or reject via `/docs`.
7. Read company status again. Rejection includes the recorded reason; approval
   satisfies `require_approved_company` on protected product operations.
8. Check invalid/duplicate CNPJ, duplicate email and a configured blocked segment.
   Form errors must preserve other input and must not create partial local rows.
