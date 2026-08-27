#!/bin/bash
set -euo pipefail

PIPELINE="${1:-Jenkinsfile.stage6-dashy-inspector-smoke}"

fail() {
  echo "FAIL: $1" >&2
  exit 2
}

[ -f "$PIPELINE" ] || fail "pipeline file missing: $PIPELINE"

echo "===== STAGE 6 JENKINS INSPECTOR SMOKE SOURCE GUARD ====="

for token in \
  "credentialsId: 'homelab-stage6-testserver-inspector'" \
  "usernameVariable: 'STAGE6_INSPECT_USER'" \
  '[ "$STAGE6_INSPECT_USER" = "homelab-stage6-inspector" ]' \
  'ping \' \
  '"inspect dashy" \' \
  'STAGE6_KNOWN_HOSTS' \
  'StrictHostKeyChecking=yes' \
  'UserKnownHostsFile="$STAGE6_KNOWN_HOSTS"' \
  "a.artifact != 'service-update-inspection'" \
  "a.mode != 'stage6-preapproval-inspect'" \
  "a.deployment?.allowed != false" \
  "a.deployment?.performed != false" \
  "a.result != 'ready-for-human-review'"
do
  grep -F -- "$token" "$PIPELINE" >/dev/null ||
    fail "required pipeline token missing: $token"
done

echo "Required read-only credential/inspection gates: PASS"

INSPECTOR_CREDENTIAL_COUNT="$(
  grep -Fc "credentialsId: 'homelab-stage6-testserver-inspector'" "$PIPELINE"
)"

[ "$INSPECTOR_CREDENTIAL_COUNT" -eq 1 ] ||
  fail "inspector credential must be bound exactly once in smoke pipeline"

if grep -F -- 'homelab-stage6-testserver-executor' "$PIPELINE" >/dev/null; then
  fail "executor credential must not appear in inspector smoke pipeline"
fi

echo "Inspector credential only; executor credential absent: PASS"

SSH_COUNT="$(grep -Ec '^[[:space:]]+ssh \\$' "$PIPELINE")"
SSH_N_COUNT="$(grep -Ec '^[[:space:]]+-n \\$' "$PIPELINE")"
DEVNULL_COUNT="$(grep -Ec '^[[:space:]]+</dev/null \\$' "$PIPELINE")"

printf 'ssh_call_count=%s\n' "$SSH_COUNT"
printf 'ssh_n_count=%s\n' "$SSH_N_COUNT"
printf 'ssh_devnull_count=%s\n' "$DEVNULL_COUNT"

[ "$SSH_COUNT" -eq 2 ] || fail "expected exactly two SSH calls"
[ "$SSH_N_COUNT" -eq 2 ] || fail "every SSH call must use -n"
[ "$DEVNULL_COUNT" -eq 2 ] || fail "every SSH call must redirect stdin from /dev/null"

echo "SSH stdin isolation: PASS"

REMOTE_PING_COUNT="$(grep -Ec '^[[:space:]]+ping \\$' "$PIPELINE")"
REMOTE_INSPECT_COUNT="$(grep -Fc '              "inspect dashy" \' "$PIPELINE")"

[ "$REMOTE_PING_COUNT" -eq 1 ] || fail "literal remote ping must appear exactly once"
[ "$REMOTE_INSPECT_COUNT" -eq 1 ] || fail "literal remote inspect dashy must appear exactly once"

for forbidden in \
  'arm dashy' \
  'deploy dashy' \
  'rollback dashy' \
  'disarm dashy' \
  'homelab-stage6-transition' \
  'homelab-stage6-execute'
do
  if grep -F -- "$forbidden" "$PIPELINE" >/dev/null; then
    fail "execution surface present in inspector smoke pipeline: $forbidden"
  fi
done

echo "Remote command surface is ping + inspect dashy only: PASS"

if grep -F -- 'input(' "$PIPELINE" >/dev/null; then
  fail "human approval input does not belong in read-only smoke pipeline"
fi

if grep -Pzoq \
  'JsonSlurperClassic\(\)\.parseText\(\s*readFile\(' \
  "$PIPELINE"
then
  fail "pipeline nests readFile inside JsonSlurperClassic.parseText; Jenkins CPS hazard"
fi

PARSE_COUNT="$(grep -c -F 'new groovy.json.JsonSlurperClassic().parseText(' "$PIPELINE")"
READ_COUNT="$(grep -c -F 'readFile(' "$PIPELINE")"

printf 'json_parse_calls=%s\n' "$PARSE_COUNT"
printf 'read_file_calls=%s\n' "$READ_COUNT"

[ "$PARSE_COUNT" -eq 1 ] || fail "unexpected JSON parse count"
[ "$READ_COUNT" -eq 1 ] || fail "unexpected readFile count"

echo "CPS-safe JSON parsing: PASS"

for token in \
  "STAGE6_ROLLBACK_REF = 'lissy93/dashy@sha256:8bef3c7bf607de54bbcd4bc3733c481b06c0053b9d12ea781e3bd29457b8b6a4'" \
  "STAGE6_ROLLBACK_IMAGE_ID = 'sha256:417b161fc4c22a4dc6759110f6794c880c72a91e4b8c64e1d653605c2726b3ee'" \
  "STAGE6_CANDIDATE_REF = 'lissy93/dashy@sha256:40e3b27369002d4bce12cdffd5136b05924e1a7ea4e0d971a890557045fb1d59'" \
  "STAGE6_CANDIDATE_IMAGE_ID = 'sha256:f7c93e5961154c8ee4a4bce7f4448d30b9ee46def5ed8eb3ebef3d111370de99'" \
  "STAGE6_CANDIDATE_PLATFORM_MANIFEST = 'sha256:cb6a9839b13481e8f96104482fed6e30f7aba186fa636a43a14cb2cb31b72e92'" \
  "STAGE6_CANDIDATE_REVISION = 'd707730b454a35c52187e824879386e1eb30f869'"
do
  grep -F -- "$token" "$PIPELINE" >/dev/null ||
    fail "immutable Dashy identity missing: $token"
done

echo "Exact immutable Dashy identities pinned: PASS"

for token in \
  "a.runtime?.invariants != 'pass'" \
  "a.runtime?.health_strategy != 'docker-health'" \
  "a.runtime?.health_result != 'healthy'" \
  'a.approval?.required != true' \
  'a.approval?.granted != false' \
  'a.deployment?.allowed != false' \
  'a.deployment?.performed != false'
do
  grep -F -- "$token" "$PIPELINE" >/dev/null ||
    fail "required read-only artifact gate missing: $token"
done

echo "Health/approval/deployment=false gates: PASS"

echo "PASS: Stage 6 Jenkins inspector smoke source guard"
