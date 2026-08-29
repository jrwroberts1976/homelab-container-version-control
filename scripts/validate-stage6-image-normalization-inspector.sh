#!/bin/bash
set -u
set -o pipefail

ROOT="$(
    cd "$(dirname "$0")/.." &&
    pwd
)"

INSPECTOR="$ROOT/ops/testserver/homelab-stage6-normalization-inspect"

fail() {
    echo "FAIL: $1"
    exit 2
}

[ -f "$INSPECTOR" ] ||
    fail "normalization inspector missing"

bash -n "$INSPECTOR" ||
    fail "normalization inspector shell syntax invalid"

for REQUIRED in \
    'normalization inspector must run as root' \
    'require_secure_root_file "$INSTALLED_SELF"' \
    'require_secure_root_file "$VALIDATOR"' \
    'require_secure_root_file "$MANIFEST"' \
    'authority Git commit mismatch' \
    'authority checkout is not clean' \
    'Compose source override is not exact tagged source image' \
    'Compose target override is not exact immutable target image' \
    'tagged source image is not local' \
    'immutable target image is not local' \
    'source and target do not resolve to identical image content' \
    'current configured image is not exact reviewed tagged source' \
    'target network membership mismatch' \
    'target published-port shape mismatch' \
    'target mount shape mismatch' \
    'target unexpectedly has Docker socket mount' \
    'health status mismatch' \
    'health marker mismatch' \
    'protected container is not running' \
    'mutation_allowed:false' \
    'allowed:false' \
    'performed:false' \
    'normalization-preflight-verified'
do
    grep -Fq "$REQUIRED" "$INSPECTOR" ||
        fail "required inspector safety gate missing: $REQUIRED"
done

echo "PASS: required read-only safety gates present"

if grep -Eiq \
    '(^|[[:space:]])docker[[:space:]]+(pull|rm|rmi|stop|start|restart|kill|create|run|tag)([[:space:]]|$)' \
    "$INSPECTOR"
then
    fail "Docker mutation command detected"
fi

if grep -Eiq \
    'docker[[:space:]]+compose.*[[:space:]](up|down|restart|stop|start|rm|pull|build)([[:space:]]|$)' \
    "$INSPECTOR"
then
    fail "Compose mutation command detected"
fi

GIT_COMMAND_COUNT="$(
    grep -Fc \
        'git -C "$AUTHORITY_ROOT" \' \
        "$INSPECTOR"
)"

[ "$GIT_COMMAND_COUNT" -eq 2 ] ||
    fail "unexpected Git command count"

grep -Fq \
    '            rev-parse HEAD 2>/dev/null' \
    "$INSPECTOR" ||
    fail "reviewed Git rev-parse command missing"

grep -Fq \
    '            status --porcelain 2>/dev/null' \
    "$INSPECTOR" ||
    fail "reviewed Git status command missing"

if grep -Eiq \
    '^[[:space:]]*git[[:space:]].*[[:space:]](checkout|switch|reset|clean|commit|merge|rebase|cherry-pick|revert)([[:space:]]|$)' \
    "$INSPECTOR"
then
    fail "direct Git mutation command detected"
fi

if grep -Eiq \
    '^[[:space:]]*(checkout|switch|reset|clean|commit|merge|rebase|cherry-pick|revert)([[:space:]]|$)' \
    "$INSPECTOR"
then
    fail "continued Git mutation verb detected"
fi

if grep -Eiq \
    '(^|[;&|[:space:]])(install|mv|cp|rm|unlink|truncate|tee)([[:space:]]|$)' \
    "$INSPECTOR"
then
    fail "filesystem mutation command detected"
fi

if grep -Eiq \
    'sed[[:space:]]+-i|perl[[:space:]]+-pi' \
    "$INSPECTOR"
then
    fail "in-place file editing command detected"
fi

echo "PASS: no mutation command surface detected"

grep -Fq \
    'docker image inspect' \
    "$INSPECTOR" ||
    fail "local image inspection missing"

grep -Fq \
    'docker compose' \
    "$INSPECTOR" ||
    fail "Compose config verification missing"

grep -Fq \
    'docker inspect' \
    "$INSPECTOR" ||
    fail "runtime inspection missing"

grep -Fq \
    'git -C "$AUTHORITY_ROOT"' \
    "$INSPECTOR" ||
    fail "authority inspection missing"

grep -Fq \
    'curl' \
    "$INSPECTOR" ||
    fail "health verification missing"

echo "PASS: expected read-only inspection capabilities present"

echo "PASS: normalization inspector source regression"
