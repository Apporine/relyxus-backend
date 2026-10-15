#!/usr/bin/env bash
# Publish a structured CI/CD event to CloudWatch Logs (visible in AWS console).
set -euo pipefail

: "${AWS_REGION:=us-east-1}"
: "${CICD_LOG_GROUP:=/relyxus/cicd/deployments}"

EVENT_TYPE="${1:?usage: publish-cicd-event.sh <build|deploy> <status>}"
STATUS="${2:?usage: publish-cicd-event.sh <build|deploy> <status>}"

GITHUB_SHA="${GITHUB_SHA:-unknown}"
GITHUB_REF_NAME="${GITHUB_REF_NAME:-unknown}"
GITHUB_RUN_ID="${GITHUB_RUN_ID:-0}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-unknown}"
GITHUB_SERVER_URL="${GITHUB_SERVER_URL:-https://github.com}"

TS="$(($(date +%s) * 1000))"
STREAM="${EVENT_TYPE}-${GITHUB_REF_NAME}-${GITHUB_SHA:0:12}-${GITHUB_RUN_ID}"
STREAM="${STREAM//\//-}"

MESSAGE="$(jq -nc \
  --arg event_type "$EVENT_TYPE" \
  --arg status "$STATUS" \
  --arg sha "$GITHUB_SHA" \
  --arg ref "$GITHUB_REF_NAME" \
  --arg run_id "$GITHUB_RUN_ID" \
  --arg repo "$GITHUB_REPOSITORY" \
  --arg run_url "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}" \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{event_type:$event_type,status:$status,git_sha:$sha,git_ref:$ref,github_run_id:$run_id,repository:$repo,run_url:$run_url,recorded_at:$ts}')"

aws logs create-log-group --log-group-name "$CICD_LOG_GROUP" --region "$AWS_REGION" 2>/dev/null || true
aws logs create-log-stream \
  --log-group-name "$CICD_LOG_GROUP" \
  --log-stream-name "$STREAM" \
  --region "$AWS_REGION" 2>/dev/null || true

EVENTS_FILE="$(mktemp)"
jq -nc --argjson ts "$TS" --arg msg "$MESSAGE" '[{timestamp:$ts,message:$msg}]' >"$EVENTS_FILE"

TOKEN="$(aws logs describe-log-streams \
  --log-group-name "$CICD_LOG_GROUP" \
  --log-stream-name-prefix "$STREAM" \
  --region "$AWS_REGION" \
  --query 'logStreams[0].uploadSequenceToken' \
  --output text)"
TOKEN="${TOKEN:-None}"

ARGS=(
  --log-group-name "$CICD_LOG_GROUP"
  --log-stream-name "$STREAM"
  --region "$AWS_REGION"
  --log-events "file://${EVENTS_FILE}"
)
if [[ "$TOKEN" != "None" && -n "$TOKEN" ]]; then
  ARGS+=(--sequence-token "$TOKEN")
fi
aws logs put-log-events "${ARGS[@]}"
rm -f "$EVENTS_FILE"

echo "Recorded ${EVENT_TYPE} (${STATUS}) to ${CICD_LOG_GROUP}/${STREAM}"
