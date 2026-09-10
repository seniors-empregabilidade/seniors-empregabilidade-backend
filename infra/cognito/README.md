# POC Cognito configuration

These JSON files are proposed AWS CLI inputs. They do not run during application
startup and have not been deployed by this PR. Use only the approved `us-east-2`
(Ohio) region and inspect existing pools before creating anything. Keep one pool
and client per environment. Do not point a seeded database at a different pool
and expect its users to be migrated.

`user-pool.json` configures case-insensitive email sign-in, email confirmation
codes, verified-email recovery, a password policy matching the POC minimum of
eight characters with uppercase/lowercase/digit/symbol requirements, and no MFA
challenge flow. The default Cognito sender is suitable for limited POC checks;
check its delivery limits before testing with the whole team. SES setup is not
included. Pool deletion protection is enabled.

`app-client.json` creates a confidential backend client with password login,
15-minute access/ID tokens, a one-day refresh token and existence-error protection.
The refresh auth flow is enabled for later session work; this API does not yet
expose refresh or logout. The browser must never receive the client secret.
These lifetimes and password rules are POC defaults proposed for review.

After the team reviews these inputs, run the following from the **backend root**
with an authorized AWS profile. Creation commands change AWS state; do not repeat
them to discover an existing pool. The profile name below is a local placeholder:

```bash
aws cognito-idp list-user-pools --max-results 60 --region us-east-2 --profile team-profile
aws cognito-idp create-user-pool --cli-input-json file://infra/cognito/user-pool.json --region us-east-2 --profile team-profile --query 'UserPool.Id' --output text
```

Replace `REPLACE_WITH_USER_POOL_ID` in a **local copy** of `app-client.json` with
the returned ID. Keep that copy outside the repository, then create the client:

```bash
aws cognito-idp create-user-pool-client --cli-input-json file:///tmp/seniors-app-client.json --region us-east-2 --profile team-profile --query 'UserPoolClient.ClientId' --output text
```

Retrieve the client secret using the AWS console and put it in the backend secret
configuration or your ignored `.env`. Do not paste it into a PR or print the full
client response into shared logs. Set `COGNITO_USER_POOL_ID` and `COGNITO_CLIENT_ID`
from these outputs. No Cognito secret or AWS credential belongs in a `VITE_*` variable.

The application uses public Cognito APIs authorized by the app client and user
credentials. It does not need AWS IAM credentials or administration permissions
for these operations. The deployment role must not receive `AdminDeleteUser` for
this implementation. A local `AWS_PROFILE` is only needed by the operator running
the provisioning commands above. IAM console accounts and application accounts
have different purposes; an AWS administrator does not become an application
administrator. Do not share console passwords or access keys for application login.

The adapter uses public Cognito operations for signup/login/confirmation and
HTTPS JWKS for token verification. Deployments need outbound HTTPS to Cognito and
BrasilAPI. After provisioning, follow the live smoke test in
[docs/IDENTITY.md](../../docs/IDENTITY.md). Only automated, isolated checks have
been performed for this PR; app-client settings and email delivery need live validation.
