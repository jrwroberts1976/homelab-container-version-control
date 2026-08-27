#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/ops/testserver/homelab-stage5-maintenance-page-helper"
TEMPLATE="$ROOT/config/stage5-maintenance-page-execution-policy.template.json"
REVIEW_WRAPPER="$ROOT/ops/testserver/homelab-stage5-pilot-ssh-review"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

bash -n "$HELPER" ||
  fail "helper shell syntax invalid"

echo "PASS: helper shell syntax"

jq -e '
  .schema_version == 1
  and .mode == "execution-template-disabled"
  and .service == "maintenance-page"
  and .deployment.allowed == false
  and .deployment.deploy_command_enabled == false
  and .deployment.rollback_command_enabled == false
  and .implementation.helper_sha256 == "REPLACE_AFTER_REVIEW"
  and .implementation.implementation_commit == "REPLACE_AFTER_REVIEW"
' "$TEMPLATE" >/dev/null ||
  fail "execution policy template is not disabled"

echo "PASS: execution policy template is disabled"

for REQUIRED in \
  'INSTALLED_SELF="/usr/local/libexec/homelab-stage5-maintenance-page"' \
  'POLICY_FILE="/etc/homelab-stage5/maintenance-page.policy.json"' \
  'ENABLE_FILE="/etc/homelab-stage5/maintenance-page.enable"' \
  'helper execution requires root' \
  'helper is not running from reviewed installed path' \
  'installed helper hash does not match policy' \
  'policy mode is not execution-enabled' \
  'policy_true '\''.deployment.allowed'\'''
do
  grep -Fq "$REQUIRED" "$HELPER" ||
    fail "required authority guard missing: $REQUIRED"
done

echo "PASS: installed-context and root-policy guards present"

if grep -nE \
  'docker compose down|docker (rm|run|exec|system|network|volume)|git (commit|push|reset|checkout|switch|merge|rebase)|(^|[^A-Za-z])eval([^A-Za-z]|$)|bash -c|sh -c' \
  "$HELPER"
then
  fail "helper contains a forbidden broad mutation primitive"
fi

echo "PASS: forbidden broad mutation primitives absent"

FORCE_COUNT="$(grep -c -- '--force-recreate' "$HELPER")"
PULL_NEVER_COUNT="$(grep -c -- '--pull never' "$HELPER")"
NO_DEPS_COUNT="$(grep -c -- '--no-deps' "$HELPER")"
NO_BUILD_COUNT="$(grep -c -- '--no-build' "$HELPER")"

[ "$FORCE_COUNT" -eq 2 ] ||
  fail "expected exactly two force-recreate operations"
[ "$PULL_NEVER_COUNT" -eq 2 ] ||
  fail "expected exactly two pull-never gates"
[ "$NO_DEPS_COUNT" -eq 2 ] ||
  fail "expected exactly two no-deps gates"
[ "$NO_BUILD_COUNT" -eq 2 ] ||
  fail "expected exactly two no-build gates"

echo "PASS: deploy/rollback command class is narrowly constrained"

grep -Fq 'fail "Stage 5 deploy command is intentionally disabled in review wrapper"' \
  "$REVIEW_WRAPPER" ||
  fail "review wrapper no longer blocks deploy"

grep -Fq 'fail "Stage 5 rollback command is intentionally disabled in review wrapper"' \
  "$REVIEW_WRAPPER" ||
  fail "review wrapper no longer blocks rollback"

echo "PASS: merged SSH review wrapper still blocks mutation"

STATUS="$(bash "$HELPER" review-status)"

printf '%s\n' "$STATUS" |
jq -e '
  .mode == "helper-source-review"
  and .service == "maintenance-page"
  and .deployment.authority_installed == false
  and .deployment.performed == false
' >/dev/null ||
  fail "review-status output is unexpected"

echo "PASS: helper review-status is non-mutating"

for ACTION in deploy rollback
do
  if bash "$HELPER" "$ACTION" >/tmp/stage5-helper-${ACTION}.out 2>&1
  then
    cat /tmp/stage5-helper-${ACTION}.out >&2
    rm -f /tmp/stage5-helper-${ACTION}.out
    fail "$ACTION unexpectedly succeeded from source checkout"
  fi

  grep -Eq \
    'helper execution requires root|helper is not running from reviewed installed path' \
    /tmp/stage5-helper-${ACTION}.out || {
      cat /tmp/stage5-helper-${ACTION}.out >&2
      rm -f /tmp/stage5-helper-${ACTION}.out
      fail "$ACTION did not fail at installed-context guard"
    }

  rm -f /tmp/stage5-helper-${ACTION}.out
  echo "PASS: $ACTION cannot execute from source checkout"
done

echo "PASS: STAGE 5 DEPLOYMENT HELPER SOURCE BOUNDARY VALIDATED"
echo "NO DEPLOYMENT AUTHORITY IS INSTALLED BY THIS SOURCE"
