#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATOR="$ROOT/scripts/validate-stage6-steady-state-manifest.py"
INSPECTOR="$ROOT/ops/testserver/homelab-stage6-steady-inspect"
MANIFEST="$ROOT/config/steady-state/homepage-2.1.2.json"
PROMETHEUS_MANIFEST="$ROOT/config/steady-state/prometheus-3.13.2.json"
SCHEMA="$ROOT/config/steady-state-manifest.schema.json"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 2
}

expect_rejected() {
    local name="$1"
    local filter="$2"
    local source="${3:-$MANIFEST}"
    local tmp
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' RETURN
    jq "$filter" "$source" > "$tmp"
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

IDS01_MANIFEST="$(mktemp)"
CONTENT_MANIFEST="$(mktemp)"
CONTAINER_HTTP_MANIFEST="$(mktemp)"
trap 'rm -f "$IDS01_MANIFEST" "$CONTENT_MANIFEST" "$CONTAINER_HTTP_MANIFEST"' EXIT

jq '
  .service.host = "ids-01"
  | .authority.compose_path = "hosts/ids-01/stacks/monitoring/docker-compose.yml"
  | .desired.platform.architecture = "amd64"
  | .health.url = "http://127.0.0.1:9090/-/ready"
' "$PROMETHEUS_MANIFEST" > "$IDS01_MANIFEST"

python3 "$VALIDATOR" "$IDS01_MANIFEST" >/dev/null ||
    fail "ids-01 synthetic steady-state manifest validation"

jq '
  .runtime.mounts = [
    {
      "type": "bind",
      "source": "/home/james/docker/data/monitoring/prometheus",
      "destination": "/etc/prometheus",
      "rw": true,
      "source_kind": "directory",
      "sha256": null
    },
    {
      "type": "bind",
      "source": "/home/james/docker/data/monitoring/prometheus/data",
      "destination": "/prometheus",
      "rw": true,
      "source_kind": "directory",
      "sha256": null
    }
  ]
  | .runtime.content_checks = [
    {
      "mount_source":
        "/home/james/docker/data/monitoring/prometheus",
      "relative_path": "prometheus.yml",
      "sha256":
        "1111111111111111111111111111111111111111111111111111111111111111"
    },
    {
      "mount_source":
        "/home/james/docker/data/monitoring/prometheus",
      "relative_path": "rules/host-health.yml",
      "sha256":
        "2222222222222222222222222222222222222222222222222222222222222222"
    }
  ]
' "$IDS01_MANIFEST" > "$CONTENT_MANIFEST"

python3 "$VALIDATOR" "$CONTENT_MANIFEST" >/dev/null ||
    fail "ids-01 steady-state content-check manifest validation"

jq '
  .health = {
    "strategy": "container-http",
    "expected": "200",
    "url": null,
    "network": "homelab_apps",
    "container_port": 9115,
    "path": "/-/healthy",
    "timeout_seconds": 360
  }
' "$IDS01_MANIFEST" > "$CONTAINER_HTTP_MANIFEST"

python3 "$VALIDATOR" "$CONTAINER_HTTP_MANIFEST" >/dev/null ||
    fail "ids-01 container-http steady-state manifest validation"

echo "PASS: syntax and positive TestServer + ids-01 + content-check + container-http validation"

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
grep -Fq 'verify_content_checks' "$INSPECTOR" || fail "content-check execution gate missing"
grep -Fq 'CONTENT_CHECKS_JSON' "$INSPECTOR" || fail "content-check evidence missing"
grep -Fq 'content check SHA-256 mismatch' "$INSPECTOR" || fail "content-check hash failure gate missing"
grep -Fq 'container-http)' "$INSPECTOR" || fail "container-http health strategy missing"
grep -Fq 'container HTTP network is not reviewed' "$INSPECTOR" || fail "container-http reviewed-network gate missing"
grep -Fq 'NetworkSettings.Networks[$network].IPAddress' "$INSPECTOR" || fail "container-http runtime IP derivation missing"
grep -Fq -- '--arg host "$MANIFEST_HOST"' "$INSPECTOR" || fail "dynamic host evidence missing"

if grep -Fq -- '--arg host "TestServer"' "$INSPECTOR"; then
    fail "steady-state inspection artifact still hardcodes TestServer"
fi

echo "PASS: required read-only inspection gates present"

expect_rejected "tagged configured image" '.desired.configured_image = "ghcr.io/gethomepage/homepage:v2.1.2"'
expect_rejected "low-risk Docker socket" '.service.risk_class = "low"'
expect_rejected "writable Docker socket" '(.runtime.mounts[] | select(.destination == "/var/run/docker.sock") | .rw) = true'
expect_rejected "alternate Docker socket source" '(.runtime.mounts[] | select(.destination == "/var/run/docker.sock") | .source) = "/tmp/docker.sock"'
expect_rejected "device-backed workload" '.runtime.devices_allowed = true'
expect_rejected "unsupported Docker host" '.service.host = "k3s-node-01"'
expect_rejected "ids-01 missing authority compose path" 'del(.authority.compose_path)' "$IDS01_MANIFEST"
expect_rejected "ids-01 absolute authority compose path" '.authority.compose_path = "/tmp/docker-compose.yml"' "$IDS01_MANIFEST"
expect_rejected "ids-01 authority path traversal" '.authority.compose_path = "hosts/ids-01/../monitoring/docker-compose.yml"' "$IDS01_MANIFEST"
expect_rejected "ids-01 wrong authority subtree" '.authority.compose_path = "stacks/monitoring/docker-compose.yml"' "$IDS01_MANIFEST"
expect_rejected "ids-01 TestServer-only health endpoint" '.health.url = "http://192.168.2.220:9090/-/ready"' "$IDS01_MANIFEST"

expect_rejected   "container-http undeclared network"   '.health.network = "unreviewed"'   "$CONTAINER_HTTP_MANIFEST"

expect_rejected   "container-http zero port"   '.health.container_port = 0'   "$CONTAINER_HTTP_MANIFEST"

expect_rejected   "container-http boolean port"   '.health.container_port = true'   "$CONTAINER_HTTP_MANIFEST"

expect_rejected   "container-http relative path"   '.health.path = "-/healthy"'   "$CONTAINER_HTTP_MANIFEST"

expect_rejected   "container-http whitespace path"   '.health.path = "/-/bad path"'   "$CONTAINER_HTTP_MANIFEST"

expect_rejected   "container-http fixed URL"   '.health.url = "http://127.0.0.1:9115/-/healthy"'   "$CONTAINER_HTTP_MANIFEST"

expect_rejected   "content check absolute relative path"   '.runtime.content_checks[0].relative_path = "/etc/passwd"'   "$CONTENT_MANIFEST"

expect_rejected   "content check traversal"   '.runtime.content_checks[0].relative_path = "../secret"'   "$CONTENT_MANIFEST"

expect_rejected   "content check undeclared mount source"   '.runtime.content_checks[0].mount_source = "/tmp"'   "$CONTENT_MANIFEST"

expect_rejected   "content check file mount source"   '
    .runtime.mounts += [
      {
        "type":"bind",
        "source":"/home/james/docker/example.txt",
        "destination":"/tmp/example.txt",
        "rw":false,
        "source_kind":"file",
        "sha256":
          "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      }
    ]
    | .runtime.content_checks[0].mount_source =
        "/home/james/docker/example.txt"
  '   "$CONTENT_MANIFEST"

expect_rejected   "content check nested mount boundary"   '
    .runtime.content_checks[0].relative_path =
      "data/wal/checkpoint"
  '   "$CONTENT_MANIFEST"

expect_rejected   "duplicate content check"   '.runtime.content_checks += [.runtime.content_checks[0]]'   "$CONTENT_MANIFEST"

expect_rejected   "invalid content check SHA"   '.runtime.content_checks[0].sha256 = "abc"'   "$CONTENT_MANIFEST"

expect_rejected "unpinned authority" '.authority.revision = "main"'
expect_rejected "Compose outside live root" '.service.compose.project_directory = "/tmp/x" | .service.compose.compose_file = "/tmp/x/docker-compose.yml"'

echo "PASS: Stage 6 steady-state source regression suite completed"
echo "NO HOST CONTACT PERFORMED"
echo "NO DOCKER COMMAND EXECUTED"
echo "NO COMPOSE COMMAND EXECUTED"
echo "NO CONTAINER CHANGED"
echo "NO UPDATE ARMED"
echo "NO DEPLOYMENT PERFORMED"
