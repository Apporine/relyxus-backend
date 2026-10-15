# Trial CI/CD on AWS

GitHub Actions runs tests and deploys to the trial EC2 host. This folder adds **AWS console visibility** and optional **CodeBuild + ECR** once your organization allows the relevant services.

## What you see in the AWS console today

| Where | What |
| ----- | ---- |
| [CloudWatch → Log groups → `/relyxus/cicd/deployments`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Frelyxus$252Fcicd$252Fdeployments) | Each `develop` deploy from GitHub Actions (JSON: sha, status, link to the workflow run) |
| [GitHub → Actions → `ci` → job `trial ec2`](https://github.com/Apporine/relyxus-backend/actions) | Full build logs and SSH deploy (unchanged) |

After the CloudFormation stack is deployed (see below):

| Where | What |
| ----- | ---- |
| [CodeBuild → `relyxus-trial-build`](https://us-east-1.console.aws.amazon.com/codesuite/codebuild/projects) | Docker image builds pushed to ECR |
| [ECR → `relyxus/api`](https://us-east-1.console.aws.amazon.com/ecr/repositories) | Built API images |
| CloudWatch → `/relyxus/cicd/codebuild` | CodeBuild stdout |

There is **no CodePipeline** in the trial stack yet (GitHub remains the orchestrator). CodePipeline can be added later if you want a pipeline view in the console.

## Org SCP blocker (account `925234975399`)

Many CI/CD APIs are **explicitly denied** by organization SCP `p-yq9ugcuf`, including `codebuild:*`, `ecr:*`, `cloudformation:ListStacks`, and `cloudwatch:PutMetricData`. **CloudWatch Logs** (`logs:CreateLogGroup`, `logs:PutLogEvents`) is allowed.

Ask your AWS organization admin to **allow** (at least in the trial account) for stack `infra/aws/cicd/cloudformation/trial-cicd.yaml`:

- `cloudformation:*` (create/update the stack)
- `codebuild:*` (project `relyxus-trial-build`)
- `ecr:*` (repository `relyxus/api`)
- `s3:*` (bucket `relyxus-cicd-source-<account-id>`)
- `iam:*` (roles in the template — or deploy via a privileged admin role)

Until then, only **CloudWatch deployment telemetry** from GitHub Actions will appear in AWS.

## One-time setup

### 1. Deploy the CloudFormation stack (when SCP allows)

From a machine with permission to create the stack:

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name relyxus-trial-cicd \
  --template-file infra/aws/cicd/cloudformation/trial-cicd.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides GitHubOrg=Apporine GitHubRepo=relyxus-backend
```

Note stack outputs: `GitHubActionsRoleArn`, `SourceBucketName`, `CodeBuildProjectName`, console URLs.

Upload a placeholder so CodeBuild’s S3 source type validates (real builds pass `sourceLocationOverride` from Actions):

```bash
echo placeholder | aws s3 cp - "s3://relyxus-cicd-source-$(aws sts get-caller-identity --query Account --output text)/placeholder.zip"
```

### 2. GitHub repository configuration

| Setting | Value |
| ------- | ----- |
| **Variable** `AWS_CICD_ROLE_ARN` | Output `GitHubActionsRoleArn` from the stack |
| **Variable** `AWS_REGION` | `us-east-1` (optional; default in workflow) |
| **Variable** `AWS_CODEBUILD_ENABLED` | `true` to start CodeBuild on each `develop` deploy (optional) |
| **Variable** `AWS_CICD_SOURCE_BUCKET` | Output `SourceBucketName` (required when CodeBuild is enabled) |

OIDC is configured in the template (`relyxus-github-actions-cicd`). No long-lived access keys are required when the role ARN variable is set.

If OIDC is blocked by SCP, use the IAM user **`relyxus-github-cicd-telemetry`** (policy in `iam/github-actions-logs-policy.json`), set repository secrets `AWS_CICD_ACCESS_KEY_ID` and `AWS_CICD_SECRET_ACCESS_KEY`, and variable `AWS_CICD_USE_ACCESS_KEY=true`.

### 3. Verify

Push to `develop`. In CloudWatch, open `/relyxus/cicd/deployments` and confirm a log stream for the run. If CodeBuild is enabled, open the CodeBuild project and confirm a build for the same commit.

## Files

- `cloudformation/trial-cicd.yaml` — ECR, CodeBuild, S3, log groups, GitHub OIDC role
- `buildspec.yml` — Docker build and ECR push
- `scripts/publish-cicd-event.sh` — deployment/build status to CloudWatch
- `iam/github-actions-cicd-policy.json` — minimal policy reference
