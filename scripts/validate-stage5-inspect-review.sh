#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$ROOT/ops/testserver/homelab-stage5-maintenance-page-authority-gate"
INSPECTOR="$ROOT/ops/testserver/homelab-stage5-maintenance-page-inspect"
SSH_WRAPPER="$ROOT/ops/testserver/homelab-stage5-pilot-ssh-inspect"
POLICY="$ROOT/config/stage5-maintenance-page-execution-policy.template.json"
STAGE4_WRAPPER="$ROOT/ops/testserver/homelab-stage4-validation-ssh"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

bash -n "$GATE" || fail "authority gate shell syntax invalid"
bash -n "$INSPECTOR" || fail "inspector shell syntax invalid"
bash -n "$SSH_WRAPPER" || fail "SSH wrapper shell syntax invalid"

echo "PASS: Stage 5 inspect source shell syntax"

jq -e '
  .schema_version == 1
  and .mode == "inspection-ready"
  and .inspection.allowed == true
  and .inspection.performed == false
  and .deployment.allowed == false
  and .deployment.performed == false
  and .deployment.deploy_command_enabled == false
  and .deployment.rollback_command_enabled == false
  and .implementation.authority_gate_sha256 == "REPLACE_AFTER_REVIEW"
  and .implementation.helper_sha256 == "REPLACE_AFTER_REVIEW"
  and .implementation.inspector_sha256 == "REPLACE_AFTER_REVIEW"
  and .implementation.implementation_commit == "REPLACE_AFTER_REVIEW"
' "$POLICY" >/dev/null ||
  fail "inspection policy template is not fail-closed"

echo "PASS: inspection policy is read-only and deployment-disabled"

for REQUIRED in \
  'INSPECTOR="/usr/local/libexec/homelab-stage5-maintenance-page-inspect"' \
  'enable file must be absent for inspection-only authority' \
  'require_inspection_installed_context' \
  'require_execution_installed_context' \
  'require_inspection_policy' \
  'require_execution_policy' \
  'exec "$INSPECTOR" inspect' \
  'exec "$INNER_HELPER" "$ACTION"'
do
  grep -Fq "$REQUIRED" "$GATE" ||
    fail "authority gate guard missing: $REQUIRED"
done

echo "PASS: authority gate separates inspect from execution paths"

INSPECTION_CONTEXT="$(
  awk '
    /^require_inspection_installed_context\(\)/ {capture=1}
    capture {print}
    capture && /^}/ {exit}
  ' "$GATE"
)"

EXECUTION_CONTEXT="$(
  awk '
    /^require_execution_installed_context\(\)/ {capture=1}
    capture {print}
    capture && /^}/ {exit}
  ' "$GATE"
)"

printf '%s\n' "$INSPECTION_CONTEXT" |
grep -Fq 'require_common_installed_context' ||
  fail "inspection context does not use common installed guards"

printf '%s\n' "$INSPECTION_CONTEXT" |
grep -Fq 'enable file must be absent for inspection-only authority' ||
  fail "inspection context does not require enable-file absence"

if printf '%s\n' "$INSPECTION_CONTEXT" |
   grep -Fq 'INNER_HELPER'
then
  fail "inspection context requires the mutating inner helper"
fi

echo "PASS: inspection context does not require deploy helper installation"

printf '%s\n' "$EXECUTION_CONTEXT" |
grep -Fq 'require_secure_root_file "$INNER_HELPER"' ||
  fail "execution context does not require the inner helper"

printf '%s\n' "$EXECUTION_CONTEXT" |
grep -Fq 'require_secure_root_file "$ENABLE_FILE"' ||
  fail "execution context does not require the enable file"

printf '%s\n' "$EXECUTION_CONTEXT" |
grep -Fq '.implementation.helper_sha256' ||
  fail "execution context does not pin the helper hash"

echo "PASS: deploy helper is required only by execution context"

if grep -nE \
  'docker compose (up|down|pull|build)|docker (pull|run|rm|restart|exec|tag|push|build|system|network|volume)|git (commit|push|reset|checkout|switch|merge|rebase)|(^|[^A-Za-z])eval([^A-Za-z]|$)|bash -c|sh -c' \
  "$GATE"
then
  fail "authority gate contains a mutation primitive"
fi

echo "PASS: authority gate itself remains non-mutating"

if grep -nE \
  'docker compose (up|down|pull|build)|docker (pull|run|rm|restart|exec|tag|push|build|system|network|volume)|git (commit|push|reset|checkout|switch|merge|rebase)|(^|[^A-Za-z])eval([^A-Za-z]|$)|bash -c|sh -c' \
  "$INSPECTOR"
then
  fail "inspector contains a mutation primitive"
fi

echo "PASS: inspector contains read-only Docker/Compose operations only"

SUDO_COUNT="$(grep -c 'exec sudo -n' "$SSH_WRAPPER")"
[ "$SUDO_COUNT" -eq 1 ] ||
  fail "inspect-only wrapper must contain exactly one sudo handoff"

grep -Fq '"inspect maintenance-page")' "$SSH_WRAPPER" ||
  fail "inspect command missing from SSH wrapper"

grep -Fq '"deploy maintenance-page")' "$SSH_WRAPPER" ||
  fail "deploy rejection missing from SSH wrapper"

grep -Fq '"rollback maintenance-page")' "$SSH_WRAPPER" ||
  fail "rollback rejection missing from SSH wrapper"

grep -Fq '"$AUTHORITY_GATE" \' "$SSH_WRAPPER" ||
  fail "SSH wrapper does not hand off to authority gate"

grep -Fq 'inspect' "$SSH_WRAPPER" ||
  fail "SSH wrapper inspect argument missing"

if grep -nE \
  'sudo -n .* (deploy|rollback)|authority-gate (deploy|rollback)' \
  "$SSH_WRAPPER"
then
  fail "inspection-only SSH wrapper exposes deployment sudo path"
fi

echo "PASS: SSH wrapper permits privileged inspect only"

for COMMAND in \
  'deploy maintenance-page' \
  'rollback maintenance-page' \
  'inspect jenkins' \
  'docker ps' \
  'shell'
do
  if SSH_ORIGINAL_COMMAND="$COMMAND" \
     bash "$SSH_WRAPPER" >/tmp/stage5-inspect-wrapper.out 2>&1
  then
    cat /tmp/stage5-inspect-wrapper.out >&2
    rm -f /tmp/stage5-inspect-wrapper.out
    fail "forbidden SSH command unexpectedly succeeded: $COMMAND"
  fi
  rm -f /tmp/stage5-inspect-wrapper.out
  echo "PASS: rejected SSH command: $COMMAND"
done

PING="$(SSH_ORIGINAL_COMMAND='ping' bash "$SSH_WRAPPER")"
printf '%s\n' "$PING" |
jq -e '
  .mode == "stage5-inspection-only"
  and .inspection.allowed == true
  and .deployment.allowed == false
  and .deployment.performed == false
' >/dev/null ||
  fail "inspection-only ping output is unexpected"

echo "PASS: inspection-only ping remains deployment-disabled"

if bash "$GATE" inspect >/tmp/stage5-gate-source-inspect.out 2>&1
then
  cat /tmp/stage5-gate-source-inspect.out >&2
  rm -f /tmp/stage5-gate-source-inspect.out
  fail "authority gate inspect unexpectedly ran from source checkout"
fi

grep -Eq \
  'authority gate execution requires root|authority gate is not running from reviewed installed path' \
  /tmp/stage5-gate-source-inspect.out || {
    cat /tmp/stage5-gate-source-inspect.out >&2
    rm -f /tmp/stage5-gate-source-inspect.out
    fail "authority gate did not fail at installed-context guard"
  }
rm -f /tmp/stage5-gate-source-inspect.out

echo "PASS: authority gate inspect cannot run from source checkout"

if bash "$INSPECTOR" inspect >/tmp/stage5-inspector-source.out 2>&1
then
  cat /tmp/stage5-inspector-source.out >&2
  rm -f /tmp/stage5-inspector-source.out
  fail "inspector unexpectedly ran from source checkout"
fi

grep -Eq \
  'inspection helper requires root|inspection helper is not running from reviewed installed path' \
  /tmp/stage5-inspector-source.out || {
    cat /tmp/stage5-inspector-source.out >&2
    rm -f /tmp/stage5-inspector-source.out
    fail "inspector did not fail at installed-context guard"
  }
rm -f /tmp/stage5-inspector-source.out

echo "PASS: inspector cannot run from source checkout"

if grep -nE \
  'docker (pull|run|rm|restart|exec|tag|push|build)|docker compose (up|down|pull|push|build)|git (commit|push|reset|checkout|switch|merge|rebase)' \
  "$STAGE4_WRAPPER"
then
  fail "Stage 4 wrapper unexpectedly contains mutation primitive"
fi

echo "PASS: Stage 4 read-only wrapper remains mutation-free"

echo "PASS: STAGE 5 INSPECTION-ONLY SOURCE BOUNDARY VALIDATED"
echo "NO DEPLOYMENT HELPER IS REQUIRED BY THE INSPECTION PATH"
echo "NO DEPLOYMENT AUTHORITY EXISTS IN THE INSPECTION-ONLY SSH PATH"
