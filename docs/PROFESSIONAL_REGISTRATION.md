# Professional registration (US-04)

Related tasks: [registration endpoint](https://app.clickup.com/t/86e308wpb),
[end-to-end integration](https://app.clickup.com/t/86e308wq1), and
[email verification](https://app.clickup.com/t/86e308wqr).

## Registration flow

1. `POST /api/v1/professionals` validates the CPF check digits, minimum age,
   accepted terms and transport fields before creating an identity.
2. PostgreSQL uniqueness constraints arbitrate duplicate CPF and email requests.
   Expected conflicts return field-specific RFC 9457 errors.
3. The service creates `app_user` and `candidate` in one local transaction, then
   asks Cognito to register the identity. Passwords are never stored locally.
4. The returned Cognito subject is linked through `app_user.identity_subject` and
   the local transaction is committed.
5. An unconfirmed identity returns `email_verification_required: true`. The client
   continues through `/api/v1/email-verification/confirm` and `/send`.

## Failure and recovery

PostgreSQL changes are atomic, but Cognito and PostgreSQL do not share a distributed
transaction. A provider failure rolls back all local registration rows. If Cognito
creates an identity before a database failure, the identity may remain even though
the local rows were rolled back. The backend emits
`identity_registration_incomplete` without logging personal data.

The backend deliberately does not delete that identity as compensation. A lost
database acknowledgement can mean the commit succeeded, so deletion could remove a
valid identity. If a confirmation code was delivered but registration returned an
error, the person can confirm the email and submit the same registration again with
the same password. The Cognito adapter authenticates the confirmed identity before
returning its existing subject; another person's password cannot claim it.

## Validation

Run all quality gates with an isolated PostgreSQL 18.4 database:

```bash
APP_ENV=test \
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/seniors_test \
RUN_DATABASE_INTEGRATION_TESTS=1 \
uv run python scripts/validate.py
```

The automated suite covers CPF validation, the exact age boundary, duplicate CPF
and email requests, concurrent requests, provider failure, local rollback, a lost
commit acknowledgement and recovery after an identity was created without local
rows. Cognito delivery to a tester-controlled mailbox remains a manual smoke check.
