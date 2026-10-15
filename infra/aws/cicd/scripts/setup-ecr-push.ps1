# One-time setup so every push to develop builds the API image in GitHub Actions and pushes it to ECR.
# Run from the repo root with an AWS admin session (`aws login`) and `gh` logged in.
# Safe to re-run: existing resources are kept and policies re-applied.
$ErrorActionPreference = "Stop"

$region = "ap-southeast-2"
$repository = "relyxus/api"
$ciUser = "relyxus-github-cicd-telemetry"
$cicd = Join-Path $PSScriptRoot ".."

function Invoke-Aws([string[]]$Arguments) {
    aws @Arguments
    if ($LASTEXITCODE -ne 0) { throw "aws $($Arguments -join ' ') failed" }
}

# ECR repository: scan on push, AES-256. Policies go through files because Windows
# PowerShell 5.1 strips quotes from JSON passed to native commands.
aws ecr describe-repositories --repository-names $repository --region $region *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Aws @("ecr", "create-repository", "--repository-name", $repository, "--region", $region,
        "--image-scanning-configuration", "scanOnPush=true", "--encryption-configuration", "encryptionType=AES256")
}
Invoke-Aws @("ecr", "put-lifecycle-policy", "--repository-name", $repository, "--region", $region,
    "--lifecycle-policy-text", "file://$cicd\ecr-lifecycle-policy.json", "--output", "text", "--query", "repositoryName")

# The GitHub Actions CI user may log in to ECR and push to this one repository.
Invoke-Aws @("iam", "put-user-policy", "--user-name", $ciUser, "--policy-name", "relyxus-ecr-push",
    "--policy-document", "file://$cicd\iam\github-ci-user-ecr-push-policy.json")

# Turn the build-and-push step on in the deploy job.
gh variable set AWS_ECR_PUSH_ENABLED --body true --repo Apporine/relyxus-backend
if ($LASTEXITCODE -ne 0) { throw "gh variable set failed" }

Write-Output "Done. The next push to develop pushes relyxus/api:<sha> and :latest to ECR."
