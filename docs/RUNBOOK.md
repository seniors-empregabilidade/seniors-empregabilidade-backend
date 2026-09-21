# Production runbook

Infrastructure lives in the `seniors-empregabilidade-infra` repository. This
document covers day-to-day operation of the running system.

## Addresses

| What | Where |
| --- | --- |
| Application | `https://main.d25fn01fvkutq4.amplifyapp.com` |
| API | `https://dabxepmbyqwfz.cloudfront.net` |
| Image registry | `951614974043.dkr.ecr.us-east-2.amazonaws.com/seniors-api` |
| Logs | CloudWatch log group `/seniors/api` |
| Region | `us-east-2`; every other region is denied by policy |

All commands below assume `export AWS_PROFILE=seniors-ages`.

## Deployment

Merging into `main` triggers CodeBuild, which builds the image, pushes it to
ECR tagged with the commit SHA, and runs `deploy.sh` on the instance through
SSM. The build fails when the deployment fails.

Deploy a specific revision by hand:

```sh
aws codebuild start-build --project-name seniors-api --region us-east-2 \
  --source-version <commit-sha>
```

## Rollback

Images are immutable and tagged by commit SHA, so rolling back means deploying
an older tag:

```sh
aws ecr describe-images --repository-name seniors-api --region us-east-2 \
  --query 'reverse(sort_by(imageDetails,&imagePushedAt))[:10].[imageTags[0],imagePushedAt]' \
  --output table

INSTANCE=$(aws ec2 describe-instances --region us-east-2 \
  --filters Name=tag:Name,Values=seniors-api Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)

aws ssm send-command --region us-east-2 --instance-ids "$INSTANCE" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["/opt/seniors/deploy.sh <older-sha>"]'
```

`deploy.sh` rolls back on its own when the new container fails its health
check, so a manual rollback is only needed for a bad revision that starts
successfully.

The frontend rolls back from the Amplify console: select the branch, pick an
earlier build, choose redeploy.

## Shell access

There is no SSH. Port 22 is closed and the instance carries no key pair.

```sh
aws ssm start-session --target "$INSTANCE" --region us-east-2
```

## Database access

The database has no public address and only accepts traffic from the API
security group. Reach it through the instance:

```sh
aws ssm start-session --target "$INSTANCE" --region us-east-2 \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["<rds-endpoint>"],"portNumber":["5432"],"localPortNumber":["15432"]}'
```

Then connect to `localhost:15432`. Credentials live in Secrets Manager under
the ARN recorded in the `/seniors/api/config` SSM parameter.

## Configuration

Non-secret configuration is the SSM parameter `/seniors/api/config`, read by
`deploy.sh` on every deployment. Changing it requires neither a rebuild nor a
new instance:

```sh
aws ssm get-parameter --name /seniors/api/config --region us-east-2 \
  --query Parameter.Value --output text
```

Redeploy the current revision for an edit to take effect.

## Test accounts

Three seeded accounts, one per flow, sharing a single password published in
the team's Discord and never committed:

| Flow | Email |
| --- | --- |
| Candidate | `candidate@example.invalid` |
| Company | `representative@company.example.invalid` |
| Administrator | `administrator@example.invalid` |

They were created with `MessageAction=SUPPRESS` and consumed none of the
Cognito daily email allowance. Recreate them with `scripts/seed_identities.py`.

## Freezing deployments

Before a presentation, stop merges from reaching production:

```sh
aws codebuild delete-webhook --project-name seniors-api --region us-east-2
aws amplify update-branch --app-id d25fn01fvkutq4 --branch-name main \
  --no-enable-auto-build --region us-east-2
```

Restore by reapplying the Terraform configuration and re-enabling auto build.

## Known limitations

Traffic between CloudFront and the instance is unencrypted, because CloudFront
requires a publicly trusted certificate on the origin and the instance has no
DNS name of its own. Login sends credentials over that leg. Closing this
requires a hostname for the origin.

The instance has 512 MB of memory and a 1 GB swap file; the API uses roughly
180 MB at rest. There is no memory alarm, because CloudWatch reports no memory
metric without an agent, and the agent would consume the memory it watches.

Cognito sends at most 50 emails per day through its default sender, covering
sign-up confirmation and password recovery.
