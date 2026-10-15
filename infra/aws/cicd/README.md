# Trial CI/CD on AWS

GitHub Actions runs the tests and deploys to the trial EC2 host. On each push to `develop` it can also build the API image in **CodeBuild** and push it to **ECR**, so the image is visible in the AWS console.

**Region:** `ap-southeast-2` (Sydney). Pick Sydney in the console region picker; ECR, CodeBuild and CloudWatch are regional.

## Flow on a push to `develop`

1. The `deploy` job signs in to AWS as the IAM user `relyxus-github-cicd-telemetry` (access key in repository secrets).
2. It records "deploy started" in CloudWatch.
3. When `AWS_CODEBUILD_ENABLED=true`, it zips the repo, uploads it to `s3://relyxus-cicd-source-925234975399/builds/<sha>/`, starts `relyxus-trial-build` and waits up to 15 minutes. CodeBuild runs `buildspec.yml`: `docker build`, then push `relyxus/api:<sha>` and `relyxus/api:latest`. A failed or timed-out build fails the job.
4. It rsyncs the repo to the EC2 host and runs `docker compose up -d --build` there. The host still builds its own image; pulling from ECR needs an instance role (not set up yet).
5. It records "deploy succeeded/failed" in CloudWatch.

## Where to look in the console

| Where | What |
| ----- | ---- |
| [ECR → `relyxus/api`](https://ap-southeast-2.console.aws.amazon.com/ecr/repositories?region=ap-southeast-2) | Built API images, tagged by commit SHA and `latest`, with scan-on-push results |
| [CodeBuild → `relyxus-trial-build`](https://ap-southeast-2.console.aws.amazon.com/codesuite/codebuild/projects/relyxus-trial-build/history?region=ap-southeast-2) | Build history |
| CloudWatch → Log groups → `/relyxus/cicd/codebuild` | Build output |
| CloudWatch → Log groups → `/relyxus/cicd/deployments` | One stream per `develop` deploy (sha, status, link to the workflow run) |
| EC2 → Instances → **Relyxus Server** → Connect → EC2 Instance Connect | Shell on the trial host; `docker ps`, `docker images` |

## Resources

| Resource | Settings |
| -------- | -------- |
| ECR `relyxus/api` | Scan on push, AES-256, keeps the 10 newest images (free tier: 500 MB) |
| S3 `relyxus-cicd-source-925234975399` | Private, encrypted, uploads expire after 7 days |
| IAM role `relyxus-trial-codebuild` | `iam/codebuild-service-policy.json`: build logs, push to `relyxus/api`, read the source bucket |
| CodeBuild `relyxus-trial-build` | `BUILD_GENERAL1_SMALL` (free tier: 100 build minutes/month), privileged for Docker builds |
| IAM user `relyxus-github-cicd-telemetry` | CloudWatch logs (`iam/github-actions-logs-policy.json`) plus `iam/github-ci-user-codebuild-policy.json`: upload sources, start/poll this one project |

## One-time setup

Account `925234975399` sits under an org SCP that denies managing the GitHub OIDC provider, so `cloudformation/trial-cicd.yaml` (which creates one) cannot be deployed there. Use the script instead. It creates the same resources minus OIDC and is safe to re-run:

```powershell
aws login                     # an admin session in 925234975399
gh auth login                 # needs permission to set repository variables
.\infra\aws\cicd\scripts\setup-trial-codebuild.ps1
```

It finishes by setting the repository variables `AWS_CODEBUILD_ENABLED=true` and `AWS_CICD_SOURCE_BUCKET`. To switch image builds off, set `AWS_CODEBUILD_ENABLED` to anything other than `true`.

In an account where the SCP allows OIDC, deploy the CloudFormation stack instead and set the variable `AWS_CICD_ROLE_ARN` to its `GitHubActionsRoleArn` output, with `AWS_CICD_USE_ACCESS_KEY` unset. No long-lived access key is needed then.

## Verify

Push to `develop` (or re-run the latest `ci` run). The `trial ec2` job log prints `CodeBuild build id: …` and then `Image: …/relyxus/api:<sha>`; the same tag appears in ECR.

## Files

- `buildspec.yml`: Docker build and ECR push (tag from `IMAGE_TAG`, passed by the workflow)
- `scripts/setup-trial-codebuild.ps1`: one-time setup for this account
- `scripts/publish-cicd-event.sh`: build and deploy status to CloudWatch
- `cloudformation/trial-cicd.yaml`: the same stack for accounts that allow OIDC
- `iam/*.json`: trust and permission policies used by the script
