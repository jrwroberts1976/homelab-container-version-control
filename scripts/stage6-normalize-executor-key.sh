#!/bin/bash
set -euo pipefail

RAW_KEY="${1:-}"
NORMALIZED_KEY="${2:-}"
EXPECTED_FINGERPRINT="${3:-}"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 2
}

[ -n "$RAW_KEY" ] ||
    fail "raw key path missing"

[ -n "$NORMALIZED_KEY" ] ||
    fail "normalized key path missing"

[ -n "$EXPECTED_FINGERPRINT" ] ||
    fail "expected fingerprint missing"

[ -r "$RAW_KEY" ] ||
    fail "raw key is not readable"

umask 077

: > "$NORMALIZED_KEY"
chmod 0600 "$NORMALIZED_KEY"

FIRST_LINE="$(
    sed -n '1p' "$RAW_KEY"
)"

SECOND_LINE="$(
    sed -n '2p' "$RAW_KEY"
)"

KEY_NORMALIZATION="none"

if [ "$FIRST_LINE" = '-----BEGIN OPENSSH PRIVATE KEY-----' ]; then
    cp "$RAW_KEY" "$NORMALIZED_KEY"

elif [ -z "$FIRST_LINE" ] &&
     [ "$SECOND_LINE" = '-----BEGIN OPENSSH PRIVATE KEY-----' ]
then
    tail -n +2 "$RAW_KEY" > "$NORMALIZED_KEY"
    KEY_NORMALIZATION="removed-one-leading-blank-line"

else
    fail "executor credential envelope is not accepted"
fi

CR_COUNT="$(
    LC_ALL=C tr -cd '\r' < "$NORMALIZED_KEY" |
    wc -c |
    tr -d ' '
)"

[ "$CR_COUNT" -eq 0 ] ||
    fail "carriage return present"

NORMALIZED_FIRST="$(
    sed -n '1p' "$NORMALIZED_KEY"
)"

NORMALIZED_LAST="$(
    awk 'NF { line=$0 } END { print line }' "$NORMALIZED_KEY"
)"

[ "$NORMALIZED_FIRST" = '-----BEGIN OPENSSH PRIVATE KEY-----' ] ||
    fail "normalized BEGIN marker invalid"

[ "$NORMALIZED_LAST" = '-----END OPENSSH PRIVATE KEY-----' ] ||
    fail "normalized END marker invalid"

LAST_BYTE="$(
    tail -c 1 "$NORMALIZED_KEY" |
    od -An -t u1 |
    tr -d ' '
)"

[ "$LAST_BYTE" = "10" ] ||
    fail "normalized key lacks final newline"

ssh-keygen \
    -y \
    -f "$NORMALIZED_KEY" \
    </dev/null \
    >/dev/null ||
    fail "normalized private key does not parse"

EXECUTOR_FP="$(
    ssh-keygen \
        -lf "$NORMALIZED_KEY" \
        -E sha256 |
    awk '{print $2}'
)"

[ "$EXECUTOR_FP" = "$EXPECTED_FINGERPRINT" ] ||
    fail "executor fingerprint mismatch"

printf '%s\n' \
    "credential_normalization=$KEY_NORMALIZATION" \
    "executor_fingerprint=$EXECUTOR_FP" \
    "carriage_return_count=$CR_COUNT" \
    'begin_marker_exact=true' \
    'end_marker_exact=true' \
    'final_newline=true' \
    'ssh_keygen_parse=PASS' \
    'private_key_contents_displayed=false'
