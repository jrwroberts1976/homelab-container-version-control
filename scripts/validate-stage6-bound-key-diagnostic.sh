#!/bin/bash
set -euo pipefail

PIPELINE="${1:-Jenkinsfile.stage6-bound-key-diagnostic}"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 2
}

[ -f "$PIPELINE" ] || fail "pipeline not found: $PIPELINE"

count_fixed() {
    local pattern="$1"
    grep -Fc -- "$pattern" "$PIPELINE" || true
}

printf '===== STAGE 6 BOUND-KEY DIAGNOSTIC SOURCE GUARD =====\n'

INSPECTOR_REFS="$(count_fixed "credentialsId: 'homelab-stage6-testserver-inspector'")"
EXECUTOR_REFS="$(count_fixed "credentialsId: 'homelab-stage6-testserver-executor'")"
SSH_REMOTE_COUNT="$(grep -Ec '^[[:space:]]+ssh[[:space:]]' "$PIPELINE" || true)"
SSH_KEYGEN_COUNT="$(grep -Fc -- 'ssh-keygen' "$PIPELINE" || true)"

echo "inspector_credential_refs=$INSPECTOR_REFS"
echo "executor_credential_refs=$EXECUTOR_REFS"
echo "remote_ssh_count=$SSH_REMOTE_COUNT"
echo "ssh_keygen_mentions=$SSH_KEYGEN_COUNT"

[ "$INSPECTOR_REFS" -eq 1 ] || fail "expected one inspector credential reference"
[ "$EXECUTOR_REFS" -eq 1 ] || fail "expected one executor credential reference"
[ "$SSH_REMOTE_COUNT" -eq 0 ] || fail "diagnostic must not open an SSH session"
[ "$SSH_KEYGEN_COUNT" -ge 2 ] || fail "expected local ssh-keygen parse/fingerprint checks"

for forbidden in \
    'inspect dashy' \
    'arm dashy' \
    'deploy dashy' \
    'rollback dashy' \
    'disarm dashy' \
    '/usr/local/libexec/homelab-stage6-'
do
    if grep -Fq -- "$forbidden" "$PIPELINE"; then
        fail "forbidden execution surface present: $forbidden"
    fi
done

if grep -Eq '(^|[[:space:]])sudo([[:space:]]|$)' "$PIPELINE"; then
    fail "pipeline contains sudo"
fi

if grep -Eq '(^|[[:space:]])docker([[:space:]]|$)' "$PIPELINE"; then
    fail "pipeline contains Docker execution"
fi

for marker in \
    "private_key_contents_displayed=false" \
    "network_activity=false" \
    "remote_command_executed=false" \
    "mutation_performed=false" \
    "begin_marker_exact=" \
    "end_marker_exact=" \
    "final_newline=" \
    "carriage_return_count=" \
    "ssh_keygen_parse=" \
    "parse_error_class="
do
    COUNT="$(count_fixed "$marker")"
    echo "$marker count=$COUNT"
    [ "$COUNT" -ge 1 ] || fail "required safe diagnostic marker missing: $marker"
done

if grep -Eq '(cat|head|tail|sed|awk|grep)[[:space:]].*STAGE6_(INSPECTOR|EXECUTOR)_KEY' "$PIPELINE"; then
    # Reads of the files for structural tests are allowed only through explicit
    # redirection. Reject obvious commands that would print key material.
    if grep -Eq '(^|[[:space:]])cat[[:space:]].*STAGE6_(INSPECTOR|EXECUTOR)_KEY' "$PIPELINE"; then
        fail "pipeline may print a private-key file"
    fi
fi

echo "PASS: Stage 6 bound-key diagnostic is local, non-mutating and secret-safe"
