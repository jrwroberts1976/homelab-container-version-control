#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATOR="$ROOT/scripts/validate-stage6-steady-state-manifest.py"
INSPECTOR="$ROOT/ops/testserver/homelab-stage6-steady-inspect"
MANIFEST="$ROOT/config/steady-state/homepage-2.1.2.json"
SCHEMA="$ROOT/config/steady-state-manifest.schema.json"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 2
}

expect_rejected() {
    local name="$1"
    local filter="$2"
    local tmp
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' RETURN
    jq "$filter" "$MANIFEST" > "$tmp"
    if python3 "$VALIDATOR" "$tmp" >/dev/null 2>&1; then
        fail "$name was accepted"
    fi
    printf 'PASS: %s -> REJECTED\n' "$name"
    rm -f "$tmp"
    trap - RETURN
}

python3 -m py_compile "$VALIDATOR" || fail "validator Python syntax"
bash -n "$INSPECTOR" || fail "inspector shell syntax"
jq -e . "$SCHEMA" >/dev/null || fail "schema JSON invalid"
jq -e . "$MANIFEST" >/dev/null || fail "Homepage steady-state JSON invalid"
python3 "$VALIDATOR" "$MANIFEST" >/dev/null || fail "Homepage steady-state manifest validation"
echo "PASS: syntax and positive manifest validation"

BANNED=(
  'docker pull'
  'docker run'
  'docker create'
  'docker start'
  'docker restart'
  'docker stop'
  'docker rm'
  'docker kill'
  'docker exec'
  'docker tag'
  'docker rmi'
  'docker image rm'
  'docker image prune'
  'docker system prune'
  'docker compose up'
  'docker compose down'
  'docker compose pull'
  'docker compose build'
  'git fetch'
  'git pull'
  'git reset'
  'git checkout'
  'git clean'
  'sudo '
  'eval '
)

for token in "${BANNED[@]}"; do
    if grep -Fq "$token" "$INSPECTOR"; then
        fail "mutating/unsafe token present in inspector: $token"
    fi
done

echo "PASS: mutating command surface absent"

grep -Fq 'docker compose' "$INSPECTOR" || fail "Compose read-only rendering missing"
grep -Fq 'config |' "$INSPECTOR" || fail "Compose config rendering missing"
grep -Fq 'docker image inspect' "$INSPECTOR" || fail "immutable image inspection missing"
grep -Fq 'docker inspect' "$INSPECTOR" || fail "runtime inspection missing"
grep -Fq 'git -C "$AUTHORITY_ROOT" rev-parse HEAD' "$INSPECTOR" || fail "authority commit gate missing"
grep -Fq 'git -C "$AUTHORITY_ROOT" status --porcelain' "$INSPECTOR" || fail "authority cleanliness gate missing"
grep -Fq 'mutation_allowed:false' "$INSPECTOR" || fail "read-only output assertion missing"
grep -Fq 'allowed:false,performed:false' "$INSPECTOR" || fail "deployment-disabled output assertion missing"
grep -Fq 'steady-state-verified' "$INSPECTOR" || fail "steady-state result missing"

echo "PASS: required read-only inspection gates present"

expect_rejected "tagged configured image" '.desired.configured_image = "ghcr.io/gethomepage/homepage:v2.1.2"'
expect_rejected "low-risk Docker socket" '.service.risk_class = "low"'
expect_rejected "writable Docker socket" '(.runtime.mounts[] | select(.destination == "/var/run/docker.sock") | .rw) = true'
expect_rejected "alternate Docker socket source" '(.runtime.mounts[] | select(.destination == "/var/run/docker.sock") | .source) = "/tmp/docker.sock"'
expect_rejected "device-backed workload" '.runtime.devices_allowed = true'
expect_rejected "wrong host backend" '.service.host = "ids-01"'
expect_rejected "unpinned authority" '.authority.revision = "main"'
expect_rejected "Compose outside live root" '.service.compose.project_directory = "/tmp/x" | .service.compose.compose_file = "/tmp/x/docker-compose.yml"'

echo "PASS: Stage 6 steady-state source regression suite completed"
echo "NO HOST CONTACT PERFORMED"
echo "NO DOCKER COMMAND EXECUTED"
echo "NO COMPOSE COMMAND EXECUTED"
echo "NO CONTAINER CHANGED"
echo "NO UPDATE ARMED"
echo "NO DEPLOYMENT PERFORMED"
