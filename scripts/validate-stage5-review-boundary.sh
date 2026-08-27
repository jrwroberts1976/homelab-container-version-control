#!/usr/bin/env bash
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WRAPPER="$ROOT/ops/testserver/homelab-stage5-pilot-ssh-review"
POLICY="$ROOT/config/stage5-maintenance-page-pilot.json"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[ -f "$WRAPPER" ] || fail "review wrapper missing"
[ -f "$POLICY" ] || fail "review policy missing"

jq -e '
  .schema_version == 1 and
  .mode == "review-only" and
  .service == "maintenance-page" and
  .deployment.allowed == false and
  .deployment.performed == false and
  .deployment.deploy_command_enabled == false and
  .deployment.rollback_command_enabled == false
' "$POLICY" >/dev/null || fail "policy is not fail-closed"

echo "PASS: review policy is fail-closed"

if grep -nE \
  'docker (pull|run|rm|restart|exec|tag|push|build)|docker compose (up|down|pull|push|build)|sudo |git (commit|push|reset|checkout|switch|merge|rebase)' \
  "$WRAPPER"
then
  fail "review wrapper contains a mutation primitive"
fi

echo "PASS: review wrapper contains no mutation primitive"

PING="$(SSH_ORIGINAL_COMMAND='ping' bash "$WRAPPER")"
INSPECT="$(SSH_ORIGINAL_COMMAND='inspect maintenance-page' bash "$WRAPPER")"

printf '%s\n' "$PING" | jq -e '
  .mode == "review-only" and
  .action == "ping" and
  .deployment.allowed == false and
  .deployment.performed == false
' >/dev/null || fail "ping contract failed"

printf '%s\n' "$INSPECT" | jq -e '
  .mode == "review-only" and
  .action == "inspect" and
  .service == "maintenance-page" and
  .deployment.allowed == false and
  .deployment.performed == false
' >/dev/null || fail "inspect contract failed"

echo "PASS: ping and inspect remain read-only"

if SSH_ORIGINAL_COMMAND='deploy maintenance-page' bash "$WRAPPER" >/dev/null 2>&1; then
  fail "deploy unexpectedly succeeded"
fi

echo "PASS: deploy is explicitly disabled"

if SSH_ORIGINAL_COMMAND='rollback maintenance-page' bash "$WRAPPER" >/dev/null 2>&1; then
  fail "rollback unexpectedly succeeded"
fi

echo "PASS: rollback is explicitly disabled"

if SSH_ORIGINAL_COMMAND='inspect jenkins' bash "$WRAPPER" >/dev/null 2>&1; then
  fail "non-pilot service unexpectedly succeeded"
fi

echo "PASS: non-pilot service is rejected"

echo "PASS: STAGE 5 REVIEW BOUNDARY VALIDATED"
echo "NO DEPLOYMENT AUTHORITY EXISTS IN THIS REVIEW WRAPPER"
