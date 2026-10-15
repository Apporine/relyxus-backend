# Trial CI/CD on AWS

GitHub Actions runs the tests and deploys to the trial EC2 host. On each push to `develop` it also builds the API image and pushes it to **ECR**, so every build is visible in the AWS console.

**Region:** `ap-southeast-2` (Sydney). Pick Sydney in the console region picker; ECR and CloudWatch are regional.

## Flow on a push to `develop`

1. The `trial ec2` job signs in to AWS as the IAM user `relyxus-github-cicd-telemetry` (access key in repository secrets).
2. It records "deploy started" in CloudWatch.
3. When `AWS_ECR_PUSH_ENABLED=true`, it builds the image on the GitHub runner and pushes `relyxus/api:<commit-sha>` and `relyxus/api:latest`. The build has no provenance or SBOM attestations, so ECR shows one row per build. A failed build fails the job, and the image URI is printed in the run summary.
4. It rsyncs the repo to the EC2 host and runs `docker compose up -d --build` there. The host still builds its own copy; pulling from ECR needs an instance role (not set up yet).
5. It records "deploy succeeded/failed" in CloudWatch.

## Where to look in the console

| Where | What |
| ----- | ---- |
| [ECR → `relyxus/api`](https://ap-southeast-2.console.aws.amazon.com/ecr/repositories/private/925234975399/relyxus/api?region=ap-southeast-2) | One image per `develop` build, tagged with the commit SHA (newest also `latest`), with scan-on-push results |
| CloudWatch → Log groups → `/relyxus/cicd/deployments` | One stream per build and deploy (sha, status, link to the workflow run) |
| EC2 → Instances → **Relyxus Server** → Connect → EC2 Instance Connect | Shell on the trial host; `docker ps`, `docker images` |

## Resources

| Resource | Settings |
| -------- | -------- |
| ECR `relyxus/api` | Scan on push, AES-256; lifecycle in `ecr-lifecycle-policy.json`: untagged images removed after 1 day, 10 newest tagged builds kept (free tier: 500 MB) |
| IAM user `relyxus-github-cicd-telemetry` | CloudWatch logs (`iam/github-actions-logs-policy.json`) and ECR push to `relyxus/api` only (`iam/github-ci-user-ecr-push-policy.json`) |

## One-time setup

Account `925234975399` sits under an org SCP that denies managing the GitHub OIDC provider, so `cloudformation/trial-cicd.yaml` (which creates one) cannot be deployed there. Use the script instead. It is safe to re-run:

```powershell
aws login                     # an admin session in 925234975399
gh auth login                 # needs permission to set repository variables
.\infra\aws\cicd\scripts\setup-ecr-push.ps1
```

It creates the repository if missing, applies the lifecycle rules, grants the CI user ECR push on `relyxus/api`, and sets the repository variable `AWS_ECR_PUSH_ENABLED=true`. To stop pushing images, set that variable to anything other than `true`.

In an account where the SCP allows OIDC, deploy the CloudFormation stack instead and set `AWS_CICD_ROLE_ARN` to its `GitHubActionsRoleArn` output with `AWS_CICD_USE_ACCESS_KEY` unset. No long-lived access key is needed then.

## Verify

Push to `develop` (or re-run the latest `ci` run on `develop`). The `trial ec2` job summary shows `Image: …/relyxus/api:<sha>`, and the same tag appears in ECR.

## Files

- `scripts/setup-ecr-push.ps1`: one-time setup for this account
- `scripts/publish-cicd-event.sh`: build and deploy status to CloudWatch
- `ecr-lifecycle-policy.json`: image retention rules
- `cloudformation/trial-cicd.yaml`: the same setup for accounts that allow OIDC
- `iam/*.json`: policies for the CI user and the OIDC role
