#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VALIDATOR="$ROOT/scripts/validate-stage6-service-manifest.py"
SCHEMA="$ROOT/config/service-update-manifest.schema.json"
BASE_MANIFEST="$ROOT/config/services/prometheus-3.13.2.json"

INSPECTOR="$ROOT/ops/testserver/homelab-stage6-inspect"
TRANSITION="$ROOT/ops/testserver/homelab-stage6-transition"
EXECUTOR="$ROOT/ops/testserver/homelab-stage6-execute"

fail() {
    echo "FAIL: $1"
    exit 2
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

expect_rejected() {
    local name="$1"
    local filter="$2"
    local candidate

    candidate="$(mktemp)"

    jq "$filter" "$TMP" > "$candidate"

    if python3 "$VALIDATOR" \
        "$candidate" \
        --schema "$SCHEMA" \
        >/dev/null 2>&1
    then
        rm -f "$candidate"
        fail "$name was accepted"
    fi

    rm -f "$candidate"

    echo "PASS: $name -> REJECTED"
}

echo "===== MULTI-HOST TRANSITION REGRESSION ====="

python3 -m py_compile "$VALIDATOR"
bash -n "$INSPECTOR"
bash -n "$TRANSITION"
bash -n "$EXECUTOR"
jq -e . "$SCHEMA" >/dev/null

echo "PASS: source syntax"

python3 "$VALIDATOR" \
    "$BASE_MANIFEST" \
    --schema "$SCHEMA" \
    >/dev/null ||
    fail "existing TestServer Prometheus manifest no longer validates"

echo "PASS: historical TestServer manifest remains valid"

jq '
  .service.host = "ids-01"

  | .authority.revision =
      "c70025add8aabf7f2806109244f079fd230ca634"

  | .authority.compose_sha256 =
      "b94ff12930efc512e08a26480bb2fa5de1a0bbeed97124aee9dd092a86cc67c1"

  | .authority.compose_path =
      "hosts/ids-01/stacks/monitoring/docker-compose.yml"

  | .versions.rollback.platform.architecture = "amd64"

  | .versions.rollback.local_image_id =
      "sha256:3c42b892cf723fa54d2f262c37a0e1f80aa8c8ddb1da7b9b0df9455a35a7f893"

  | .versions.candidate.platform.architecture = "amd64"

  | .versions.candidate.platform_manifest_digest =
      "sha256:1147c92841726a6fef55fe6124491d6f85480f8de204f7d420304ca5bbd0a8f7"

  | .versions.candidate.config_digest =
      "sha256:8da6d95a8747c08872fbffa86d35a9c39433cbe908ce8e5939ad34087cceac86"

  | .versions.candidate.local_image_id =
      "sha256:508729e0e2d18e11fd742a5a5ca70e557b940a93948c3c95fd0123a6fd538b69"

  | .versions.candidate.created =
      "2026-07-30T12:01:58.514082203Z"

  | .runtime.networks = ["monitoring"]

  | .runtime.published_ports = [
      {
        "host_ip": "0.0.0.0",
        "host_port": 9090,
        "container_port": 9090,
        "protocol": "tcp"
      },
      {
        "host_ip": "::",
        "host_port": 9090,
        "container_port": 9090,
        "protocol": "tcp"
      }
    ]

  | .runtime.mounts = [
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

  | .health.url =
      "http://127.0.0.1:9090/-/ready"

  | .protection.containers =
      ["grafana", "loki"]
' "$BASE_MANIFEST" > "$TMP"

python3 "$VALIDATOR" \
    "$TMP" \
    --schema "$SCHEMA" \
    >/dev/null ||
    fail "synthetic ids-01 AMD64 manifest rejected"

echo "PASS: synthetic ids-01 AMD64 transition manifest"

expect_rejected \
    "unsupported host" \
    '.service.host = "k3s-node-01"'

expect_rejected \
    "ids-01 missing authority path" \
    'del(.authority.compose_path)'

expect_rejected \
    "ids-01 absolute authority path" \
    '.authority.compose_path = "/tmp/docker-compose.yml"'

expect_rejected \
    "ids-01 authority traversal" \
    '.authority.compose_path = "hosts/ids-01/../monitoring/docker-compose.yml"'

expect_rejected \
    "ids-01 wrong authority subtree" \
    '.authority.compose_path = "stacks/monitoring/docker-compose.yml"'

expect_rejected \
    "ids-01 ARM64 rollback" \
    '.versions.rollback.platform.architecture = "arm64"'

expect_rejected \
    "ids-01 ARM64 candidate" \
    '.versions.candidate.platform.architecture = "arm64"'

expect_rejected \
    "ids-01 missing candidate local image ID" \
    'del(.versions.candidate.local_image_id)'

expect_rejected \
    "ids-01 remote HTTP health" \
    '.health.url = "http://192.168.2.220:9090/-/ready"'

expect_rejected \
    "ids-01 missing Grafana protection" \
    '.protection.containers = ["loki"]'

echo
echo "===== HELPER CONTRACT ====="

for FILE in \
    "$INSPECTOR" \
    "$TRANSITION" \
    "$EXECUTOR"
do
    grep -F \
      'CURRENT_HOST="$(hostname -s)"' \
      "$FILE" \
      >/dev/null ||
        fail "local host gate missing from $FILE"

    grep -F \
      'manifest host does not match local machine' \
      "$FILE" \
      >/dev/null ||
        fail "host mismatch rejection missing from $FILE"

    grep -F \
      'CANDIDATE_LOCAL_ID=' \
      "$FILE" \
      >/dev/null ||
        fail "candidate local ID gate missing from $FILE"
done

grep -F \
  'authority.compose_path // ""' \
  "$INSPECTOR" \
  >/dev/null ||
    fail "inspector authority-path support missing"

grep -F \
  'authority.compose_path // ""' \
  "$EXECUTOR" \
  >/dev/null ||
    fail "executor authority-path support missing"

grep -F \
  'verify_runtime_shape "$CANDIDATE_LOCAL_ID" "$CANDIDATE_REF"' \
  "$EXECUTOR" \
  >/dev/null ||
    fail "executor does not deploy against candidate local image ID"

if grep -Fq \
  'verify_runtime_shape "$CANDIDATE_CONFIG_DIGEST" "$CANDIDATE_REF"' \
  "$EXECUTOR"
then
    fail "executor still treats candidate config digest as Docker image ID"
fi

if grep -Fq \
  '[ "$current_image" = "$CANDIDATE_CONFIG_DIGEST" ]' \
  "$EXECUTOR"
then
    fail "rollback still treats config digest as Docker image ID"
fi

echo "PASS: Docker local image ID separated from config digest"

echo
echo "===== RESULT ====="
echo "PASS: Stage 6 multi-host transition source regression complete"
echo "TestServer=arm64"
echo "ids-01=amd64"
echo "ids01_authority_path_required=true"
echo "ids01_candidate_local_id_required=true"
echo "docker29_index_id_supported=true"
echo "NO HOST CONTACT PERFORMED"
echo "NO DOCKER COMMAND EXECUTED"
echo "NO COMPOSE COMMAND EXECUTED"
echo "NO FILE INSTALLED"
echo "NO UPDATE ARMED"
echo "NO DEPLOYMENT PERFORMED"
