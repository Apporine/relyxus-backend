# One-time setup of the trial image build: GitHub Actions -> S3 -> CodeBuild -> ECR.
# Run from the repo root with an AWS admin session (`aws login`) and `gh` logged in.
# Safe to re-run: every step skips what already exists and re-applies policies.
#
# Used instead of cloudformation/trial-cicd.yaml in account 925234975399 because the
# org SCP denies managing the GitHub OIDC provider, which that template creates.
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$account = "925234975399"
$region = "ap-southeast-2"
$repository = "relyxus/api"
$bucket = "relyxus-cicd-source-$account"
$project = "relyxus-trial-build"
$buildRole = "relyxus-trial-codebuild"
$ciUser = "relyxus-github-cicd-telemetry"
$iam = Join-Path $PSScriptRoot "..\iam"

function Test-AwsResource([scriptblock]$Probe) {
    & $Probe *> $null
    return $LASTEXITCODE -eq 0
}

function Invoke-Aws([string[]]$Arguments) {
    aws @Arguments
    if ($LASTEXITCODE -ne 0) { throw "aws $($Arguments -join ' ') failed" }
}

# ECR repository: scan on push, keep the 10 newest images (free tier: 500 MB).
if (-not (Test-AwsResource { aws ecr describe-repositories --repository-names $repository --region $region })) {
    Invoke-Aws @("ecr", "create-repository", "--repository-name", $repository, "--region", $region,
        "--image-scanning-configuration", "scanOnPush=true", "--encryption-configuration", "encryptionType=AES256")
}
# Policies go through files: Windows PowerShell 5.1 strips quotes from JSON passed to native commands.
$ecrLifecycle = Join-Path $env:TEMP "relyxus-ecr-lifecycle.json"
'{"rules":[{"rulePriority":1,"description":"Keep the 10 most recent images","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":10},"action":{"type":"expire"}}]}' |
    Set-Content -Encoding ascii $ecrLifecycle
Invoke-Aws @("ecr", "put-lifecycle-policy", "--repository-name", $repository, "--region", $region,
    "--lifecycle-policy-text", "file://$ecrLifecycle", "--output", "text", "--query", "repositoryName")

# Source bucket: private, encrypted by default, uploads expire after 7 days.
if (-not (Test-AwsResource { aws s3api head-bucket --bucket $bucket })) {
    Invoke-Aws @("s3api", "create-bucket", "--bucket", $bucket, "--region", $region,
        "--create-bucket-configuration", "LocationConstraint=$region")
}
Invoke-Aws @("s3api", "put-public-access-block", "--bucket", $bucket, "--public-access-block-configuration",
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true")
$s3Lifecycle = Join-Path $env:TEMP "relyxus-s3-lifecycle.json"
'{"Rules":[{"ID":"expire-build-sources","Status":"Enabled","Filter":{"Prefix":""},"Expiration":{"Days":7}}]}' |
    Set-Content -Encoding ascii $s3Lifecycle
Invoke-Aws @("s3api", "put-bucket-lifecycle-configuration", "--bucket", $bucket,
    "--lifecycle-configuration", "file://$s3Lifecycle")
# CodeBuild requires its default S3 source to exist; real builds override the location.
$placeholderText = Join-Path $env:TEMP "relyxus-placeholder.txt"
$placeholderZip = Join-Path $env:TEMP "relyxus-placeholder.zip"
"placeholder" | Set-Content $placeholderText
Compress-Archive -Path $placeholderText -DestinationPath $placeholderZip -Force
Invoke-Aws @("s3", "cp", $placeholderZip, "s3://$bucket/placeholder.zip", "--only-show-errors")

# CodeBuild service role: build logs, push to relyxus/api, read the source bucket only.
if (-not (Test-AwsResource { aws iam get-role --role-name $buildRole })) {
    Invoke-Aws @("iam", "create-role", "--role-name", $buildRole,
        "--assume-role-policy-document", "file://$iam\codebuild-trust-policy.json")
    Start-Sleep -Seconds 10  # IAM propagation before CodeBuild can assume the role
}
Invoke-Aws @("iam", "put-role-policy", "--role-name", $buildRole, "--policy-name", $buildRole,
    "--policy-document", "file://$iam\codebuild-service-policy.json")

# CodeBuild project on the free-tier SMALL compute type.
$environment = "type=LINUX_CONTAINER,image=aws/codebuild/standard:7.0,computeType=BUILD_GENERAL1_SMALL," +
    "privilegedMode=true,environmentVariables=[{name=AWS_DEFAULT_REGION,value=$region}," +
    "{name=AWS_ACCOUNT_ID,value=$account},{name=ECR_REPOSITORY,value=$repository}]"
$projectArguments = @("--name", $project, "--region", $region,
    "--source", "type=S3,location=$bucket/placeholder.zip,buildspec=infra/aws/cicd/buildspec.yml",
    "--artifacts", "type=NO_ARTIFACTS", "--environment", $environment,
    "--service-role", "arn:aws:iam::${account}:role/$buildRole",
    "--logs-config", "cloudWatchLogs={status=ENABLED,groupName=/relyxus/cicd/codebuild}",
    "--output", "text", "--query", "project.arn")
$existing = aws codebuild batch-get-projects --names $project --region $region --query "projects[0].name" --output text
if ($existing -eq $project) {
    Invoke-Aws (@("codebuild", "update-project") + $projectArguments)
} else {
    Invoke-Aws (@("codebuild", "create-project") + $projectArguments)
}

# The CI user may upload sources and start/poll this one project.
Invoke-Aws @("iam", "put-user-policy", "--user-name", $ciUser, "--policy-name", "relyxus-trial-codebuild-start",
    "--policy-document", "file://$iam\github-ci-user-codebuild-policy.json")

# Turn the build step on in GitHub Actions.
gh variable set AWS_CODEBUILD_ENABLED --body true --repo Apporine/relyxus-backend
gh variable set AWS_CICD_SOURCE_BUCKET --body $bucket --repo Apporine/relyxus-backend

Write-Output "Done. The next push to develop builds the image into ECR -> $repository."
