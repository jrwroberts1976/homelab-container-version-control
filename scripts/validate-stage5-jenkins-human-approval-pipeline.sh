#!/bin/bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

PIPELINE="Jenkinsfile.stage5-maintenance-page-pilot"
DESIGN="docs/stage5-jenkins-human-approval-pipeline.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 2
}

for file in "$PIPELINE" "$DESIGN"; do
  [ -f "$file" ] || fail "missing source file: $file"
done

git rev-parse --verify origin/main >/dev/null 2>&1 ||
  fail "origin/main unavailable; fetch before review"

echo "===== STAGE 5 JENKINS HUMAN-APPROVAL PIPELINE SOURCE REVIEW ====="
echo "head=$(git rev-parse HEAD)"
echo "origin_main=$(git rev-parse origin/main)"
echo

echo "===== EXISTING PROVEN SOURCE UNCHANGED ====="

git diff --exit-code origin/main...HEAD -- \
  Jenkinsfile \
  ops/testserver/homelab-stage4-validation-ssh \
  ops/testserver/homelab-stage5-maintenance-page-authority-gate \
  ops/testserver/homelab-stage5-maintenance-page-helper \
  ops/testserver/homelab-stage5-maintenance-page-inspect \
  ops/testserver/homelab-stage5-pilot-ssh-inspect \
  ops/testserver/homelab-stage5-maintenance-page-transition \
  ops/testserver/homelab-stage5-executor-ssh \
  config/stage5-maintenance-page-execution-enabled.template.json \
  >/dev/null ||
  fail "existing Stage 4/Stage 5 implementation source changed"

echo "Existing Stage 4 + Stage 5 implementation source unchanged: PASS"
echo

echo "===== APPROVAL / CREDENTIAL ORDERING ====="

INPUT_LINE="$(grep -n -F 'def approver = input(' "$PIPELINE" | cut -d: -f1)"
REINSPECT_LINE="$(grep -n -F "stage('Re-inspect after approval')" "$PIPELINE" | cut -d: -f1)"
DRIFT_LINE="$(grep -n -F "stage('Assert no drift after approval')" "$PIPELINE" | cut -d: -f1)"
FIRST_EXECUTOR_LINE="$(grep -n -F "credentialsId: 'homelab-stage5-testserver-executor'" "$PIPELINE" | head -1 | cut -d: -f1)"
FIRST_INSPECTOR_LINE="$(grep -n -F "credentialsId: 'homelab-stage5-testserver-inspector'" "$PIPELINE" | head -1 | cut -d: -f1)"
SECOND_INSPECTOR_LINE="$(grep -n -F "credentialsId: 'homelab-stage5-testserver-inspector'" "$PIPELINE" | sed -n '2p' | cut -d: -f1)"

for value in \
  "$INPUT_LINE" \
  "$REINSPECT_LINE" \
  "$DRIFT_LINE" \
  "$FIRST_EXECUTOR_LINE" \
  "$FIRST_INSPECTOR_LINE" \
  "$SECOND_INSPECTOR_LINE"
do
  [[ "$value" =~ ^[0-9]+$ ]] || fail "pipeline ordering marker missing"
done

[ "$FIRST_INSPECTOR_LINE" -lt "$INPUT_LINE" ] ||
  fail "first inspection credential is not before approval"

[ "$INPUT_LINE" -lt "$REINSPECT_LINE" ] ||
  fail "reinspection does not occur after approval"

[ "$REINSPECT_LINE" -lt "$SECOND_INSPECTOR_LINE" ] ||
  fail "second inspector credential is not in reinspection stage"

[ "$SECOND_INSPECTOR_LINE" -lt "$DRIFT_LINE" ] ||
  fail "drift assertion does not follow second inspection"

[ "$DRIFT_LINE" -lt "$FIRST_EXECUTOR_LINE" ] ||
  fail "executor credential appears before second inspection/drift gate"

INPUT_COUNT="$(grep -c -F 'def approver = input(' "$PIPELINE")"
INSPECTOR_COUNT="$(grep -c -F "credentialsId: 'homelab-stage5-testserver-inspector'" "$PIPELINE")"
EXECUTOR_COUNT="$(grep -c -F "credentialsId: 'homelab-stage5-testserver-executor'" "$PIPELINE")"

[ "$INPUT_COUNT" -eq 1 ] || fail "pipeline must contain exactly one human input step"
[ "$INSPECTOR_COUNT" -eq 2 ] || fail "pipeline must bind inspector credential exactly twice"
[ "$EXECUTOR_COUNT" -eq 4 ] || fail "pipeline must bind executor credential exactly four times"

grep -Fq "submitter: 'james'" "$PIPELINE" ||
  fail "input step is not restricted to james"

grep -Fq "submitterParameter: 'APPROVED_BY'" "$PIPELINE" ||
  fail "input step does not record approver"

grep -Fq "timeout(time: 60, unit: 'MINUTES')" "$PIPELINE" ||
  fail "approval step does not have bounded timeout"

echo "Inspector -> input -> reinspection -> drift gate -> executor ordering: PASS"
echo

echo "===== EXACT PILOT IDENTITY PINS ====="

for literal in \
  "STAGE5_PILOT_ID = 'stage5-maintenance-page-nginx-1.31.4-20260827'" \
  "STAGE5_SERVICE = 'maintenance-page'" \
  "STAGE5_AUTHORITY_COMMIT = 'f0430e1d9ee91ba4dfba7db34d0e9f0e201a8883'" \
  "STAGE5_ROLLBACK = 'nginx@sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752'" \
  "STAGE5_CANDIDATE = 'nginx@sha256:db35bfc6b2951e7f8a72db5db120288c127ffaeeb4a6d4b95a26fead017d5913'" \
  "STAGE5_EXECUTION_POLICY_SHA256 = 'e8c629e34d16a02b2dc9a979dbe50da47dace810875bbc3296cead6285af2bc5'" \
  "STAGE5_HOSTKEY_FINGERPRINT = 'SHA256:PEDpP7QlmSztJSIYHzZ+YuIT7XurmpeWp85wRnlfZuk'"
do
  grep -Fq "$literal" "$PIPELINE" ||
    fail "missing exact Stage 5 pipeline pin: $literal"
done

echo "Exact pilot/image/policy/host-key identities pinned: PASS"
echo

echo "===== CPS-SAFE JSON PARSING ====="

if grep -Pzoq \
  'JsonSlurperClassic\(\)\.parseText\(\s*readFile\(' \
  "$PIPELINE"
then
  fail "pipeline nests readFile inside JsonSlurperClassic.parseText; Jenkins CPS serialization hazard"
fi

PARSE_COUNT="$(grep -c -F 'new groovy.json.JsonSlurperClassic().parseText(' "$PIPELINE")"
READ_COUNT="$(grep -c -F 'readFile(' "$PIPELINE")"

printf 'json_parse_calls=%s\n' "$PARSE_COUNT"
printf 'read_file_calls=%s\n' "$READ_COUNT"

[ "$PARSE_COUNT" -eq 7 ] ||
  fail "unexpected JsonSlurperClassic parse-call count"

[ "$READ_COUNT" -eq 7 ] ||
  fail "unexpected readFile call count"

echo "No readFile pipeline step is nested inside JsonSlurperClassic.parseText: PASS"
echo

echo "===== LITERAL REMOTE ACTION SURFACE ====="

for action in \
  '"inspect maintenance-page"' \
  '"arm maintenance-page"' \
  '"deploy maintenance-page"' \
  '"rollback maintenance-page"' \
  '"disarm maintenance-page"'
do
  grep -Fq "$action" "$PIPELINE" ||
    fail "missing literal remote action: $action"
done

if grep -En \
  'ssh .*\$\{?[A-Za-z_][A-Za-z0-9_]*\}? maintenance-page|eval |sudo |docker (ps|run|exec|restart|rm|pull|compose)|MAINTENANCE_PAGE_IMAGE=' \
  "$PIPELINE"
then
  fail "pipeline contains an out-of-scope local mutation/arbitrary remote construct"
fi

if grep -Eq '\$@|\$\*' "$PIPELINE"; then
  fail "pipeline forwards arbitrary shell arguments"
fi

if grep -Fq 'parameters {' "$PIPELINE"; then
  fail "pilot pipeline unexpectedly exposes user parameters"
fi

echo "Only literal reviewed remote actions are present: PASS"
echo

echo "===== FAIL-CLOSED RECOVERY CONTRACT ====="

grep -Fq 'reviewed rollback will be attempted' "$PIPELINE" ||
  fail "deploy failure does not enter reviewed rollback path"

grep -Fq 'Execution remains armed for controlled manual recovery' "$PIPELINE" ||
  fail "rollback failure does not preserve controlled recovery authority"

grep -Fq "stage('Disarm terminal state')" "$PIPELINE" ||
  fail "terminal disarm stage missing"

grep -Fq "env.STAGE5_DEPLOY_RC == '0' || env.STAGE5_ROLLBACK_RC == '0'" "$PIPELINE" ||
  fail "disarm is not gated on proven deploy/rollback success"

echo "Deploy failure -> reviewed rollback; rollback failure -> fail closed armed: PASS"
echo

echo "===== ARTIFACT CONTRACT ====="

for artifact in \
  'stage5-inspection-before-approval.json' \
  'stage5-critical-before-approval.json' \
  'stage5-approval.txt' \
  'stage5-inspection-after-approval.json' \
  'stage5-critical-after-approval.json' \
  'stage5-arm.json' \
  'stage5-deploy.json' \
  'stage5-rollback.json' \
  'stage5-disarm.json'
do
  grep -Fq "$artifact" "$PIPELINE" ||
    fail "pipeline artifact missing: $artifact"
done

grep -Fq "artifacts: 'artifacts/stage5-*'" "$PIPELINE" ||
  fail "Stage 5 artifacts are not archived"

echo "Inspection/approval/execution evidence artifacts: PASS"
echo

echo "===== SOURCE-ONLY REVIEW HASH ====="

PIPELINE_SHA="$(sha256sum "$PIPELINE" | awk '{print $1}')"

printf 'pipeline_sha256=%s\n' "$PIPELINE_SHA"

echo
echo "===== RESULT ====="
echo "PASS: existing Stage 4/Stage 5 implementation source unchanged"
echo "PASS: executor credential cannot be bound before human approval + second inspection"
echo "PASS: approval restricted to james and recorded"
echo "PASS: exact immutable pilot identities pinned"
echo "PASS: Jenkins CPS-unsafe nested readFile/parseText pattern rejected"
echo "PASS: only literal inspect/arm/deploy/rollback/disarm actions"
echo "PASS: rollback/disarm failure handling is fail closed"
echo "PASS: source-only review; no live Jenkins job or sudo authority changed"
echo "NO STAGE 5 DEPLOYMENT PERFORMED"
