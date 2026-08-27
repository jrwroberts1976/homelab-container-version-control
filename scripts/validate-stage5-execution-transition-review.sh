#!/bin/bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

TRANSITION="ops/testserver/homelab-stage5-maintenance-page-transition"
EXECUTOR="ops/testserver/homelab-stage5-executor-ssh"
POLICY="config/stage5-maintenance-page-execution-enabled.template.json"
DESIGN="docs/stage5-human-approved-execution-transition.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 2
}

for file in "$TRANSITION" "$EXECUTOR" "$POLICY" "$DESIGN"; do
  [ -f "$file" ] || fail "missing review source: $file"
done

echo "===== STAGE 5 EXECUTION-TRANSITION SOURCE REVIEW ====="
echo "head=$(git rev-parse HEAD)"
echo

echo "===== EXISTING PROVEN BOUNDARY UNCHANGED ====="

git diff --exit-code main -- \
  Jenkinsfile \
  ops/testserver/homelab-stage4-validation-ssh \
  ops/testserver/homelab-stage5-maintenance-page-authority-gate \
  ops/testserver/homelab-stage5-maintenance-page-helper \
  ops/testserver/homelab-stage5-maintenance-page-inspect \
  ops/testserver/homelab-stage5-pilot-ssh-inspect \
  config/stage5-maintenance-page-execution-policy.template.json \
  >/dev/null ||
  fail "existing Stage 4/Stage 5 proven source changed"

echo "Existing Stage 4 + inspection source unchanged: PASS"
echo

echo "===== EXECUTION POLICY TEMPLATE ====="

jq -e '
  .schema_version == 1
  and .mode == "execution-enabled"
  and .pilot_id == "stage5-maintenance-page-nginx-1.31.4-20260827"
  and .service == "maintenance-page"
  and .host == "TestServer"
  and .docker_env_authority_commit == "f0430e1d9ee91ba4dfba7db34d0e9f0e201a8883"
  and .images.rollback == "nginx@sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752"
  and .images.candidate == "nginx@sha256:db35bfc6b2951e7f8a72db5db120288c127ffaeeb4a6d4b95a26fead017d5913"
  and .inspection.allowed == true
  and .deployment.allowed == true
  and .deployment.performed == false
  and .deployment.deploy_command_enabled == true
  and .deployment.rollback_command_enabled == true
' "$POLICY" >/dev/null ||
  fail "execution policy semantics mismatch"

PLACEHOLDERS="$(grep -o 'REPLACE_AFTER_REVIEW' "$POLICY" | wc -l | tr -d ' ')"
[ "$PLACEHOLDERS" -eq 6 ] ||
  fail "execution policy does not contain exactly six review placeholders"

echo "Execution policy semantics + disabled review placeholders: PASS"
echo

echo "===== EXECUTOR WRAPPER ALLOW-LIST ====="

for literal in \
  '"ping")' \
  '"arm maintenance-page")' \
  '"deploy maintenance-page")' \
  '"rollback maintenance-page")' \
  '"disarm maintenance-page")' \
  '"inspect maintenance-page")'
do
  grep -Fq "$literal" "$EXECUTOR" ||
    fail "executor wrapper missing literal branch: $literal"
done

for forbidden in \
  'eval ' \
  'bash -c' \
  'sh -c' \
  'docker ' \
  'docker-compose' \
  'docker compose' \
  'SSH_ORIGINAL_COMMAND=' \
  'exec $' \
  'sudo -S'
do
  if grep -Fq "$forbidden" "$EXECUTOR"; then
    fail "executor wrapper contains forbidden construct: $forbidden"
  fi
done

if grep -E '\$@|\$\*' "$EXECUTOR" >/dev/null; then
  fail "executor wrapper forwards arbitrary arguments"
fi

grep -Fq 'inspection is not available through the Stage 5 executor identity' "$EXECUTOR" ||
  fail "executor does not explicitly reject inspection"

echo "Executor wrapper literal allow-list / no arbitrary forwarding: PASS"
echo

echo "===== TRANSITION HELPER MUTATION BOUNDARY ====="

for expected in \
  'INSTALLED_SELF="/usr/local/libexec/homelab-stage5-maintenance-page-transition"' \
  'ACTIVE_POLICY="/etc/homelab-stage5/maintenance-page.policy.json"' \
  'EXECUTION_POLICY="/etc/homelab-stage5/maintenance-page.execution-policy.json"' \
  'ENABLE_FILE="/etc/homelab-stage5/maintenance-page.enable"' \
  'STATE_DIR="/var/lib/homelab-stage5/maintenance-page"' \
  'EXPECTED_INSPECTION_POLICY_SHA256="REPLACE_AFTER_REVIEW"' \
  'EXPECTED_EXECUTION_POLICY_SHA256="REPLACE_AFTER_REVIEW"'
do
  grep -Fq "$expected" "$TRANSITION" ||
    fail "transition source missing required gate: $expected"
done

if grep -En \
  'docker (pull|run|rm|restart|exec|tag|push|build)|docker compose (up|down|pull|push|build|restart|rm)|git (commit|push|reset|checkout|switch|merge|rebase)|systemctl (start|stop|restart|reload)|apt(-get)? |curl .*(-X|--request)' \
  "$TRANSITION"
then
  fail "transition helper contains an out-of-scope mutation primitive"
fi

if grep -E '\$@|\$\*|eval ' "$TRANSITION" >/dev/null; then
  fail "transition helper accepts/forwards arbitrary arguments"
fi

for action in 'arm)' 'disarm)'; do
  grep -Fq "$action" "$TRANSITION" ||
    fail "transition helper missing action: $action"
done

grep -Fq 'fail "action not permitted"' "$TRANSITION" ||
  fail "transition helper has no default deny"

echo "Transition helper limited to policy/activation state changes: PASS"
echo

echo "===== SOURCE CHECKOUT CANNOT ARM ====="

set +e
SOURCE_OUTPUT="$(bash "$TRANSITION" arm 2>&1)"
SOURCE_RC=$?
set -e

printf '%s\n' "$SOURCE_OUTPUT"
echo "source_arm_rc=$SOURCE_RC"

[ "$SOURCE_RC" -ne 0 ] ||
  fail "transition helper unexpectedly armed from source checkout"

echo "Source-checkout arm rejected: PASS"
echo

echo "===== REVIEW HASHES ====="

printf 'transition_sha256=%s\n' "$(sha256sum "$TRANSITION" | awk '{print $1}')"
printf 'executor_wrapper_sha256=%s\n' "$(sha256sum "$EXECUTOR" | awk '{print $1}')"
printf 'execution_policy_template_sha256=%s\n' "$(sha256sum "$POLICY" | awk '{print $1}')"

echo
echo=""
echo "===== RESULT ====="
echo "PASS: source-only transition design preserves existing inspection boundary"
echo "PASS: execution policy still contains review placeholders"
echo "PASS: executor wrapper exposes only literal Stage 5 actions"
echo "PASS: transition helper contains no container mutation primitive"
echo "PASS: source checkout cannot arm execution"
echo "NO HOST INSTALLATION PERFORMED"
echo "NO SUDO AUTHORITY CHANGED"
echo "NO JENKINS JOB CHANGED"
echo "NO STAGE 5 DEPLOYMENT PERFORMED"
