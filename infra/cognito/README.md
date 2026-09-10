# Cognito environment

The pool and confidential backend app client are provisioned in `us-east-2` (Ohio).
[`environment.json`](environment.json) contains their public identifiers. The client secret and test
passwords are outside Git. Use the existing pool for team testing; the JSON inputs
are configuration references, not commands to create duplicate resources.

The pool uses email sign-in without case sensitivity, confirmation codes, the
Cognito default email sender, verified-email recovery and a password policy of at
least eight characters with uppercase/lowercase letters, digits and symbols.
MFA is disabled in this development environment; the API does not implement challenge responses.
Pool deletion protection is active.

The backend client enables password login, 15-minute access/ID tokens and a one-day
refresh token. Refresh capability is configured in Cognito; API refresh/logout
endpoints remain separate work. `PreventUserExistenceErrors` and token revocation
are enabled. The browser must never receive the client secret.

## Team setup

1. Open the existing pool in the AWS console, in Ohio.
2. Select the `seniors-backend-poc` app client and obtain its secret using your
   authorized AWS access. Do not paste it in Discord or a PR.
3. Set `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` and
   `COGNITO_CLIENT_SECRET` in the ignored backend `.env`.
4. Apply migrations to your local PostgreSQL and follow
   [the API test flow](../../docs/IDENTITY.md#configuring-a-developer-environment).

IAM credentials are used by infrastructure operators. Application login/signup
uses public Cognito operations with the app client and user credentials. The
application does not need permission to create pools or administer users.

Three synthetic test accounts were prepared for candidate, company and administrator
testing. Invitation emails were suppressed and confirmation was administrative.
Real login, JWT verification and the local user lookup are checked separately from
email delivery. A controlled mailbox test is still required to verify receipt of
confirmation/reset messages. Do not use shared synthetic accounts for real data.
