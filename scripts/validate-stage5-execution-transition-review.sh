#!/bin/bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

TRANSITION="ops/testserver/homelab-stage5-maintenance-page-transition"
EXECUTOR="ops/testserver/homelab-stage5-executor-ssh"
POLICY="config/stage5-maintenance-page-execution-enabled.template.json"
DESIGN="docs/stage5-human-approved-execution-transition.md"

REVIEW_COMMIT="7918c6c4ed01c32333c781e6d9de3eeaa19e4773"
EXPECTED_TRANSITION_SHA256="73eb78453b87e86760cb9fafd556e11c2a5c43c8df2b2d3e87fa0429902d64d1"
EXPECTED_EXECUTOR_SHA256="2feea261deaccb92dccc1f9c982ed9f4360c6320ad84dba2d7b39e476582dc49"
EXPECTED_GATE_SHA256="561499a0e327f02e4df7fdabf40ab1d0660dc5ed51622061c568f9deaaa4dbda"
EXPECTED_HELPER_SHA256="a0df7b46aa01ffc9ef3fbf43cea43caeef34681ef22b759ae822ed2832cfc42a"
EXPECTED_INSPECTOR_SHA256="64dc6526e66a9e6878ca23c1703a9d7bb11c82b7f60cf7b8aae714b2ed9cb213"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 2
}

for file in "$TRANSITION" "$EXECUTOR" "$POLICY" "$DESIGN"; do
  [ -f "$file" ] || fail "missing review source: $file"
done

git rev-parse --verify origin/main >/dev/null 2>&1 ||
  fail "origin/main is unavailable; fetch before review"

git cat-file -e "${REVIEW_COMMIT}^{commit}" 2>/dev/null ||
  fail "reviewed implementation commit is unavailable"

git merge-base --is-ancestor "$REVIEW_COMMIT" HEAD ||
  fail "reviewed implementation commit is not an ancestor of HEAD"

echo "===== STAGE 5 EXECUTION-TRANSITION PINNED SOURCE REVIEW ====="
echo "head=$(git rev-parse HEAD)"
echo "origin_main=$(git rev-parse origin/main)"
echo "review_commit=$REVIEW_COMMIT"
echo

echo "===== REVIEWED IMPLEMENTATION SOURCE FROZEN ====="

git diff --exit-code "$REVIEW_COMMIT"..HEAD -- \
  "$TRANSITION" \
  "$EXECUTOR" \
  "$DESIGN" \
  >/dev/null ||
  fail "reviewed transition/executor/design source changed after review"

TRANSITION_SHA="$(sha256sum "$TRANSITION" | awk '{print $1}')"
EXECUTOR_SHA="$(sha256sum "$EXECUTOR" | awk '{print $1}')"

[ "$TRANSITION_SHA" = "$EXPECTED_TRANSITION_SHA256" ] ||
  fail "transition helper hash changed after review"

[ "$EXECUTOR_SHA" = "$EXPECTED_EXECUTOR_SHA256" ] ||
  fail "executor wrapper hash changed after review"

echo "Reviewed transition/executor source unchanged: PASS"
echo

echo "===== EXISTING PROVEN BOUNDARY UNCHANGED ====="

git diff --exit-code origin/main...HEAD -- \
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

echo "===== PINNED EXECUTION POLICY ====="

jq -e \
  --arg review_commit "$REVIEW_COMMIT" \
  --arg gate "$EXPECTED_GATE_SHA256" \
  --arg helper "$EXPECTED_HELPER_SHA256" \
  --arg inspector "$EXPECTED_INSPECTOR_SHA256" '
  .schema_version == 1
  and .mode == "execution-enabled"
  and .pilot_id == "stage5-maintenance-page-nginx-1.31.4-20260827"
  and .service == "maintenance-page"
  and .host == "TestServer"
  and .compose_project == "maintenance-page"
  and .compose_file == "/home/james/docker/stacks/maintenance-page/docker-compose.yml"
  and .docker_env_authority_commit == "f0430e1d9ee91ba4dfba7db34d0e9f0e201a8883"
  and .docker_env_authority_checkout == "/var/lib/homelab-stage5/authority/docker-env"
  and .configuration.compose_sha256 == "26fb63ff74360932f0dbf9eb27876c67bb3212767aaa6a11ea6c3370750eeadf"
  and .configuration.nginx_config_sha256 == "5f776d04e520489a0958d2f267dcf034448a3c385b88f142ae7aa67d53a34d13"
  and .configuration.index_html_sha256 == "9497b740f24af80568843efdf500544a25b47f4dd3fe248161c31c4cd202eb29"
  and .images.rollback == "nginx@sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752"
  and .images.candidate == "nginx@sha256:db35bfc6b2951e7f8a72db5db120288c127ffaeeb4a6d4b95a26fead017d5913"
  and .images.candidate_arm64_manifest == "sha256:57744b8fa99abc438b1fbde6bd69e4270d0984ccfdee60c661ec22243047373a"
  and .implementation.authority_gate_sha256 == $gate
  and .implementation.helper_sha256 == $helper
  and .implementation.inspector_sha256 == $inspector
  and .implementation.implementation_commit == $review_commit
  and .inspection.allowed == true
  and .inspection.performed == false
  and .deployment.allowed == true
  and .deployment.performed == false
  and .deployment.deploy_command_enabled == true
  and .deployment.rollback_command_enabled == true
' "$POLICY" >/dev/null ||
  fail "pinned execution policy semantics mismatch"

if grep -Fq 'REPLACE_AFTER_REVIEW' "$POLICY"; then
  fail "execution policy still contains a review placeholder"
fi

if jq -e '
  .implementation
  | has("transition_sha256") or has("executor_wrapper_sha256")
' "$POLICY" >/dev/null; then
  fail "execution policy contains circular transition/executor hash fields"
fi

echo "Pinned execution policy exact + non-circular: PASS"
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

echo "===== TRANSITION HELPER INTEGRITY + MUTATION BOUNDARY ====="

for expected in \
  'INSTALLED_SELF="/usr/local/libexec/homelab-stage5-maintenance-page-transition"' \
  'ACTIVE_POLICY="/etc/homelab-stage5/maintenance-page.policy.json"' \
  'EXECUTION_POLICY="/etc/homelab-stage5/maintenance-page.execution-policy.json"' \
  'ENABLE_FILE="/etc/homelab-stage5/maintenance-page.enable"' \
  'STATE_DIR="/var/lib/homelab-stage5/maintenance-page"' \
  'EXPECTED_INSPECTION_POLICY_SHA256="adcac66121b04d4b0b4f0a9962c5e75e5c9b3a801a5b28f222f04a6670973f6f"' \
  'EXPECTED_AUTHORITY_GATE_SHA256="561499a0e327f02e4df7fdabf40ab1d0660dc5ed51622061c568f9deaaa4dbda"' \
  'EXPECTED_DEPLOY_HELPER_SHA256="a0df7b46aa01ffc9ef3fbf43cea43caeef34681ef22b759ae822ed2832cfc42a"' \
  'EXPECTED_INSPECTOR_SHA256="64dc6526e66a9e6878ca23c1703a9d7bb11c82b7f60cf7b8aae714b2ed9cb213"'
do
  grep -Fq "$expected" "$TRANSITION" ||
    fail "transition source missing required exact gate: $expected"
done

if grep -Fq 'EXPECTED_EXECUTION_POLICY_SHA256=' "$TRANSITION"; then
  fail "transition helper reintroduced circular execution-policy hash pin"
fi

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

grep -Fq 'trap cleanup_arm EXIT' "$TRANSITION" ||
  fail "arm transition lacks EXIT rollback trap"

grep -Fq 'install -o root -g root -m 0600 "$backup" "$ACTIVE_POLICY"' "$TRANSITION" ||
  fail "arm transition lacks inspection-policy restore path"

grep -Fq 'active policy does not exactly match staged execution policy' "$TRANSITION" ||
  fail "arm transition does not verify byte-exact staged policy copy"

echo "Transition helper exact component pins: PASS"
echo "Transition helper has no container mutation primitive: PASS"
echo "Arm partial-failure restore path: PASS"
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

echo "===== FINAL SOURCE LOCK ====="

POLICY_SHA="$(sha256sum "$POLICY" | awk '{print $1}')"

printf 'review_commit=%s\n' "$REVIEW_COMMIT"
printf 'transition_sha256=%s\n' "$TRANSITION_SHA"
printf 'executor_wrapper_sha256=%s\n' "$EXECUTOR_SHA"
printf 'execution_policy_sha256=%s\n' "$POLICY_SHA"
printf 'authority_gate_sha256=%s\n' "$EXPECTED_GATE_SHA256"
printf 'helper_sha256=%s\n' "$EXPECTED_HELPER_SHA256"
printf 'inspector_sha256=%s\n' "$EXPECTED_INSPECTOR_SHA256"

echo
echo "===== RESULT ====="
echo "PASS: reviewed implementation source is frozen"
echo "PASS: final execution policy is fully pinned"
echo "PASS: existing Stage 4 and Stage 5 inspection source unchanged"
echo "PASS: executor wrapper exposes only literal Stage 5 actions"
echo "PASS: transition helper changes only activation/policy state"
echo "PASS: source checkout cannot arm execution"
echo "NO HOST INSTALLATION PERFORMED"
echo "NO SUDO AUTHORITY CHANGED"
echo "NO JENKINS JOB CHANGED"
echo "NO STAGE 5 DEPLOYMENT PERFORMED"
