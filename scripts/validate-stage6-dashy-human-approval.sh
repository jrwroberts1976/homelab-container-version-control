#!/bin/bash
set -euo pipefail

PIPELINE="${1:-Jenkinsfile.stage6-dashy-human-approval}"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 2
}

[ -f "$PIPELINE" ] || fail "pipeline not found: $PIPELINE"

count_fixed() {
    local pattern="$1"
    grep -Fc -- "$pattern" "$PIPELINE" || true
}

first_line() {
    local pattern="$1"
    grep -nF -- "$pattern" "$PIPELINE" |
        head -1 |
        cut -d: -f1
}

require_count() {
    local expected="$1" pattern="$2" label="$3" actual
    actual="$(count_fixed "$pattern")"
    printf '%s=%s\n' "$label" "$actual"
    [ "$actual" -eq "$expected" ] ||
        fail "$label expected $expected, got $actual"
}

require_present() {
    local pattern="$1" label="$2"
    grep -Fq -- "$pattern" "$PIPELINE" || fail "$label missing"
}

printf '===== STAGE 6 DASHY HUMAN-APPROVAL SOURCE GUARD =====\n'

printf '\n===== STAGE ORDER =====\n'

CHECKOUT_LINE="$(first_line "stage('Checkout')")"
PREFLIGHT_LINE="$(first_line "stage('Source and host-key preflight')")"
INSPECT_LINE="$(first_line "stage('Pre-approval inspection')")"
ASSERT_LINE="$(first_line "stage('Assert pre-approval artifact')")"
APPROVAL_LINE="$(first_line "stage('Human approval')")"
REINSPECT_LINE="$(first_line "stage('Re-inspect after approval')")"
DRIFT_LINE="$(first_line "stage('Assert zero drift after approval')")"
EXECUTOR_PING_LINE="$(first_line "stage('Executor preflight after approval')")"
ARM_LINE="$(first_line "stage('Arm exact update')")"
DEPLOY_LINE="$(first_line "stage('Deploy exact candidate')")"
ROLLBACK_LINE="$(first_line "stage('Rollback on deploy failure')")"
DISARM_LINE="$(first_line "stage('Disarm terminal state')")"
FINAL_LINE="$(first_line "stage('Final pipeline result')")"

for value in \
    "$CHECKOUT_LINE" "$PREFLIGHT_LINE" "$INSPECT_LINE" "$ASSERT_LINE" \
    "$APPROVAL_LINE" "$REINSPECT_LINE" "$DRIFT_LINE" "$EXECUTOR_PING_LINE" \
    "$ARM_LINE" "$DEPLOY_LINE" "$ROLLBACK_LINE" "$DISARM_LINE" "$FINAL_LINE"
do
    [ -n "$value" ] || fail "required stage missing"
done

[ "$CHECKOUT_LINE" -lt "$PREFLIGHT_LINE" ] || fail "checkout/preflight order"
[ "$PREFLIGHT_LINE" -lt "$INSPECT_LINE" ] || fail "preflight/inspection order"
[ "$INSPECT_LINE" -lt "$ASSERT_LINE" ] || fail "inspection/assert order"
[ "$ASSERT_LINE" -lt "$APPROVAL_LINE" ] || fail "assert/approval order"
[ "$APPROVAL_LINE" -lt "$REINSPECT_LINE" ] || fail "approval/reinspection order"
[ "$REINSPECT_LINE" -lt "$DRIFT_LINE" ] || fail "reinspection/drift order"
[ "$DRIFT_LINE" -lt "$EXECUTOR_PING_LINE" ] || fail "executor bound before zero-drift gate"
[ "$EXECUTOR_PING_LINE" -lt "$ARM_LINE" ] || fail "executor preflight/arm order"
[ "$ARM_LINE" -lt "$DEPLOY_LINE" ] || fail "arm/deploy order"
[ "$DEPLOY_LINE" -lt "$ROLLBACK_LINE" ] || fail "deploy/rollback order"
[ "$ROLLBACK_LINE" -lt "$DISARM_LINE" ] || fail "rollback/disarm order"
[ "$DISARM_LINE" -lt "$FINAL_LINE" ] || fail "disarm/final order"

echo "Stage ordering: PASS"

printf '\n===== HUMAN APPROVAL BOUNDARY =====\n'

require_count 1 "def approver = input(" human_approval_input_count
require_count 1 "submitter: 'james'" human_approval_submitter_count
require_present "submitterParameter: 'APPROVED_BY'" "approval submitter parameter"
require_present "env.STAGE6_APPROVED_BY != 'james'" "approval identity assertion"
require_present "timeout(time: 60, unit: 'MINUTES')" "approval timeout"

echo "Human approval boundary: PASS"

printf '\n===== CREDENTIAL ORDERING =====\n'

require_count 2 "credentialsId: 'homelab-stage6-testserver-inspector'" inspector_credential_refs
require_count 5 "credentialsId: 'homelab-stage6-testserver-executor'" executor_credential_refs

FIRST_EXECUTOR_LINE="$(first_line "credentialsId: 'homelab-stage6-testserver-executor'")"
[ -n "$FIRST_EXECUTOR_LINE" ] || fail "executor credential reference missing"
[ "$FIRST_EXECUTOR_LINE" -gt "$DRIFT_LINE" ] ||
    fail "executor credential referenced before zero-drift stage"

if sed -n "1,${DRIFT_LINE}p" "$PIPELINE" |
    grep -Fq -- "credentialsId: 'homelab-stage6-testserver-executor'"
then
    fail "executor credential is visible before zero-drift gate"
fi

echo "Credential ordering: PASS"

printf '\n===== REMOTE COMMAND SURFACE =====\n'

require_count 2 '"inspect dashy"' remote_inspect_count
require_count 1 '"arm dashy"' remote_arm_count
require_count 1 '"deploy dashy"' remote_deploy_count
require_count 1 '"rollback dashy"' remote_rollback_count
require_count 1 '"disarm dashy"' remote_disarm_count

PING_COUNT="$(grep -Ec '^[[:space:]]+ping \\$' "$PIPELINE" || true)"
echo "remote_ping_count=$PING_COUNT"
[ "$PING_COUNT" -eq 1 ] || fail "expected one executor ping"

echo "Remote command surface: PASS"

printf '\n===== SSH FAIL-CLOSED OPTIONS =====\n'

SSH_COUNT="$(grep -Ec '^[[:space:]]+ssh \\$' "$PIPELINE" || true)"
SSH_N_COUNT="$(grep -Ec '^[[:space:]]+-n \\$' "$PIPELINE" || true)"
DEVNULL_COUNT="$(grep -Ec '^[[:space:]]+</dev/null( \\)?$' "$PIPELINE" || true)"

echo "ssh_count=$SSH_COUNT"
echo "ssh_n_count=$SSH_N_COUNT"
echo "ssh_devnull_count=$DEVNULL_COUNT"

[ "$SSH_COUNT" -eq 7 ] || fail "expected seven SSH calls"
[ "$SSH_N_COUNT" -eq "$SSH_COUNT" ] || fail "not every SSH call uses -n"
[ "$DEVNULL_COUNT" -eq "$SSH_COUNT" ] || fail "not every SSH call redirects stdin"

for option in \
    'IdentitiesOnly=yes' \
    'BatchMode=yes' \
    'PasswordAuthentication=no' \
    'KbdInteractiveAuthentication=no' \
    'StrictHostKeyChecking=yes' \
    'UserKnownHostsFile="$STAGE6_KNOWN_HOSTS"'
do
    count="$(count_fixed "$option")"
    echo "$option count=$count"
    [ "$count" -eq "$SSH_COUNT" ] || fail "SSH option missing from one or more calls: $option"
done

echo "SSH fail-closed options: PASS"

printf '\n===== CPS-SAFE JSON PARSING =====\n'

if grep -Eq 'parseText[[:space:]]*\([[:space:]]*readFile' "$PIPELINE"; then
    fail "nested parseText(readFile()) is prohibited"
fi

PARSE_COUNT="$(count_fixed 'JsonSlurperClassic().parseText(')"
READ_COUNT="$(count_fixed 'readFile(')"

echo "json_parse_count=$PARSE_COUNT"
echo "read_file_count=$READ_COUNT"

[ "$PARSE_COUNT" -ge 6 ] || fail "expected explicit artifact parsing stages"
[ "$READ_COUNT" -ge "$PARSE_COUNT" ] || fail "parse calls are not backed by separate readFile calls"

echo "CPS-safe JSON parsing: PASS"

printf '\n===== IMMUTABLE IDENTITY PINS =====\n'

for value in \
    '868062eef746f0418a53be7370ca539444d67454' \
    'f659d556365e47288fc99aeb74a1a5a78c2f1852' \
    '54d18c2d78fb80d04649271d5422cb886777f9b8ed5d4ef41d50217462876010' \
    'lissy93/dashy@sha256:8bef3c7bf607de54bbcd4bc3733c481b06c0053b9d12ea781e3bd29457b8b6a4' \
    'sha256:417b161fc4c22a4dc6759110f6794c880c72a91e4b8c64e1d653605c2726b3ee' \
    'lissy93/dashy@sha256:40e3b27369002d4bce12cdffd5136b05924e1a7ea4e0d971a890557045fb1d59' \
    'sha256:f7c93e5961154c8ee4a4bce7f4448d30b9ee46def5ed8eb3ebef3d111370de99' \
    'sha256:cb6a9839b13481e8f96104482fed6e30f7aba186fa636a43a14cb2cb31b72e92' \
    'd707730b454a35c52187e824879386e1eb30f869' \
    'stage6-dashy-40e3b27369002d4bce12cdffd5136b05924e1a7ea4e0d971a890557045fb1d59'
do
    require_present "$value" "immutable identity $value"
done

echo "Immutable identity pins: PASS"

printf '\n===== FAIL-CLOSED EXECUTION CONTRACT =====\n'

require_present "a.approval?.granted != false" "approval false precondition"
require_present "a.deployment?.allowed != false" "deployment false precondition"
require_present "if (before != after)" "zero-drift comparison"
require_present "returnStatus: true" "controlled deploy/rollback status"
require_present "reviewed rollback path will be attempted" "rollback branch"
require_present "Execution remains armed/consumed for controlled manual recovery" "failed rollback terminal warning"
require_present "a.consumed != true" "consumed artifact assertion"
require_present "a.deployment_authority_remains_armed != true" "armed-after-execution assertion"
require_present "a.deployment_authority != false" "disarm assertion"
require_present "archiveArtifacts(" "artifact archival"

if grep -Eq '(^|[[:space:]])sudo([[:space:]]|$)' "$PIPELINE"; then
    fail "pipeline contains local sudo"
fi

if grep -Eq '(^|[[:space:]])docker([[:space:]]|$)' "$PIPELINE"; then
    fail "pipeline contains local Docker execution"
fi

if grep -Fq -- '/usr/local/libexec/homelab-stage6-' "$PIPELINE"; then
    fail "pipeline bypasses forced-command SSH wrapper"
fi

echo "Fail-closed execution contract: PASS"

printf '\n===== RESULT =====\n'
printf 'PASS: Stage 6 Dashy human-approval pipeline source guard\n'
