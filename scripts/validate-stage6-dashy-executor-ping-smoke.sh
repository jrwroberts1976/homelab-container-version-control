#!/bin/bash
set -euo pipefail

PIPELINE="${1:-Jenkinsfile.stage6-dashy-executor-ping-smoke}"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 2
}

[ -f "$PIPELINE" ] || fail "pipeline not found: $PIPELINE"

count_fixed() {
    local pattern="$1"
    grep -Fc -- "$pattern" "$PIPELINE" || true
}

printf '===== STAGE 6 EXECUTOR PING SMOKE SOURCE GUARD =====\n'

EXECUTOR_REFS="$(count_fixed "credentialsId: 'homelab-stage6-testserver-executor'")"
INSPECTOR_REFS="$(count_fixed "credentialsId: 'homelab-stage6-testserver-inspector'")"
SSH_COUNT="$(grep -Ec '^[[:space:]]+ssh \\$' "$PIPELINE" || true)"
SSH_N_COUNT="$(grep -Ec '^[[:space:]]+-n \\$' "$PIPELINE" || true)"
DEVNULL_COUNT="$(grep -Ec '^[[:space:]]+</dev/null \\$' "$PIPELINE" || true)"
PING_COUNT="$(grep -Ec '^[[:space:]]+ping \\$' "$PIPELINE" || true)"
NORMALIZED_IDENTITY_COUNT="$(count_fixed '-i "$NORMALIZED_EXECUTOR_KEY"')"
RAW_IDENTITY_COUNT="$(count_fixed '-i "$STAGE6_EXECUTOR_KEY"')"

echo "executor_credential_refs=$EXECUTOR_REFS"
echo "inspector_credential_refs=$INSPECTOR_REFS"
echo "ssh_count=$SSH_COUNT"
echo "ssh_n_count=$SSH_N_COUNT"
echo "ssh_devnull_count=$DEVNULL_COUNT"
echo "remote_ping_count=$PING_COUNT"
echo "normalized_identity_count=$NORMALIZED_IDENTITY_COUNT"
echo "raw_identity_count=$RAW_IDENTITY_COUNT"

[ "$EXECUTOR_REFS" -eq 1 ] || fail "expected one executor credential reference"
[ "$INSPECTOR_REFS" -eq 0 ] || fail "inspector credential must not be referenced"
[ "$SSH_COUNT" -eq 1 ] || fail "expected exactly one SSH call"
[ "$SSH_N_COUNT" -eq 1 ] || fail "SSH call must use -n"
[ "$DEVNULL_COUNT" -eq 1 ] || fail "SSH call must redirect stdin"
[ "$PING_COUNT" -eq 1 ] || fail "expected exactly one remote ping command"
[ "$NORMALIZED_IDENTITY_COUNT" -eq 1 ] || fail "SSH must use normalized executor key exactly once"
[ "$RAW_IDENTITY_COUNT" -eq 0 ] || fail "raw Jenkins-bound key must never be passed to SSH"

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
    [ "$count" -eq 1 ] || fail "SSH option count mismatch: $option"
done

for marker in \
    "STAGE6_EXECUTOR_FINGERPRINT = 'SHA256:A9VBS2vpB6+OvA62GhWXIMTgsNc2DdqOUX4eqLR58gY'" \
    'NORMALIZED_EXECUTOR_KEY="$(mktemp "${WORKSPACE}/.stage6-executor-key.XXXXXX")"' \
    'trap '\''rm -f "$NORMALIZED_EXECUTOR_KEY"'\'' EXIT HUP INT TERM' \
    "[ \"\$FIRST_LINE\" = '-----BEGIN OPENSSH PRIVATE KEY-----' ]" \
    '[ -z "$FIRST_LINE" ]' \
    "[ \"\$SECOND_LINE\" = '-----BEGIN OPENSSH PRIVATE KEY-----' ]" \
    'tail -n +2 "$STAGE6_EXECUTOR_KEY" > "$NORMALIZED_EXECUTOR_KEY"' \
    'KEY_NORMALIZATION=removed-one-leading-blank-line' \
    'CR_COUNT="$(LC_ALL=C tr -cd '\''\r'\'' < "$NORMALIZED_EXECUTOR_KEY" | wc -c | tr -d '\'' '\'')"' \
    "[ \"\$NORMALIZED_FIRST\" = '-----BEGIN OPENSSH PRIVATE KEY-----' ]" \
    "[ \"\$NORMALIZED_LAST\" = '-----END OPENSSH PRIVATE KEY-----' ]" \
    'ssh-keygen -y -f "$NORMALIZED_EXECUTOR_KEY" >/dev/null' \
    'ssh-keygen -lf "$NORMALIZED_EXECUTOR_KEY" -E sha256' \
    '[ "$EXECUTOR_FP" = "$STAGE6_EXECUTOR_FINGERPRINT" ]' \
    'private_key_contents_displayed=false'
do
    COUNT="$(count_fixed "$marker")"
    echo "$marker count=$COUNT"
    [ "$COUNT" -ge 1 ] || fail "required canonicalization guard missing: $marker"
done

for forbidden in \
    '"inspect dashy"' \
    '"arm dashy"' \
    '"deploy dashy"' \
    '"rollback dashy"' \
    '"disarm dashy"'
do
    if grep -Fq -- "$forbidden" "$PIPELINE"; then
        fail "forbidden remote command present: $forbidden"
    fi
done

if grep -Eq '(^|[[:space:]])sudo([[:space:]]|$)' "$PIPELINE"; then
    fail "pipeline contains local sudo"
fi

if grep -Eq '(^|[[:space:]])docker([[:space:]]|$)' "$PIPELINE"; then
    fail "pipeline contains local Docker execution"
fi

if grep -Fq -- '/usr/local/libexec/homelab-stage6-' "$PIPELINE"; then
    fail "pipeline bypasses forced-command SSH wrapper"
fi

grep -Fq -- "[ \"\$(tr -d '\\\\r\\\\n' < artifacts/stage6-executor-ping.txt)\" = \"pong\" ]" "$PIPELINE" ||
    fail "pong assertion missing"

grep -Fq -- "'mutation_performed=false'" "$PIPELINE" ||
    fail "non-mutation evidence marker missing"

echo "PASS: Stage 6 executor ping smoke canonicalizes at most one leading blank line, fingerprints the key, and remains ping-only"
