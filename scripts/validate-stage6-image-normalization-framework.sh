#!/bin/bash
set -u
set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VALIDATOR="$ROOT/scripts/validate-stage6-image-normalization.py"
SCHEMA="$ROOT/config/service-image-normalization-manifest.schema.json"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
    echo "FAIL: $1"
    exit 2
}

make_manifest() {
    local host="$1"
    local arch="$2"
    local image_id="$3"
    local health="$4"
    local output="$5"

    python3 - \
        "$host" \
        "$arch" \
        "$image_id" \
        "$health" \
        "$output" <<'PY'
import json
import sys

host, arch, image_id, health_kind, output = sys.argv[1:]

repo = "prom/blackbox-exporter"
digest = (
    "sha256:"
    "e753ff9f3fc458d02cca5eddab5a77e1c175eee484a8925ac7d524f04366c2fc"
)
tag = f"{repo}:v0.28.0"
immutable = f"{repo}@{digest}"

if host == "TestServer":
    authority = {
        "repository": "docker-env",
        "revision": "d1ca9a5e10d151893573fd97d6a5c282ba912a1e",
        "compose_sha256":
            "b8a895bd8e23c9f528cf9209f70368be42bf53f8044cbd99ef35eae188e3d68b",
    }
    project_directory = "/home/james/docker/stacks/monitoring"
    compose_file = (
        "/home/james/docker/stacks/monitoring/docker-compose.yml"
    )
    networks = ["homelab_apps"]
    ports = [{
        "host_ip": "192.168.2.220",
        "host_port": 9115,
        "container_port": 9115,
        "protocol": "tcp",
    }]
    config_sha = (
        "ab065eba6778f9a0b3b85d1c85712c47b36c342574b9d05f4d29cfa9a7098836"
    )
    protection = ["jenkins", "jenkins-docker"]
else:
    authority = {
        "repository": "docker-env",
        "revision": "d1ca9a5e10d151893573fd97d6a5c282ba912a1e",
        "compose_sha256":
            "128a8e842a2b1bc54b966b93aac9d11ba1d7c0cc7d8eb89282c7f2ffa1f89ae9",
        "compose_path":
            "hosts/ids-01/stacks/monitoring/docker-compose.yml",
    }
    project_directory = "/home/james/docker/stacks/monitoring"
    compose_file = (
        "/home/james/docker/stacks/monitoring/docker-compose.yml"
    )
    networks = ["monitoring"]
    ports = []
    config_sha = (
        "8303b38676d0253c2a782e586c165d5d39feca32cc1f186d240435f09b0fc9b0"
    )
    protection = ["grafana", "loki"]

if health_kind == "http":
    health = {
        "strategy": "http",
        "url": "http://192.168.2.220:9115/-/healthy",
        "expected_status": 200,
        "marker": "Healthy",
        "timeout_seconds": 30,
    }
else:
    health = {
        "strategy": "container-http",
        "network": "monitoring",
        "container_port": 9115,
        "path": "/-/healthy",
        "expected_status": 200,
        "marker": "Healthy",
        "timeout_seconds": 30,
    }

manifest = {
    "schema_version": 1,
    "artifact": "service-image-normalization-manifest",
    "mode": "stage6-image-ref-normalization",
    "service": {
        "name": "blackbox-exporter",
        "container": "blackbox-exporter",
        "host": host,
        "image_type": "registry-image",
        "risk_class": "low",
        "compose": {
            "project": "monitoring",
            "service": "blackbox-exporter",
            "project_directory": project_directory,
            "compose_file": compose_file,
            "image_variable": "BLACKBOX_EXPORTER_IMAGE",
        },
    },
    "authority": authority,
    "image": {
        "version": "0.28.0",
        "repository": repo,
        "source": {
            "configured_image": tag,
            "local_image_id": image_id,
        },
        "target": {
            "configured_image": immutable,
            "index_digest": digest,
            "local_image_id": image_id,
        },
        "rollback": {
            "configured_image": tag,
            "local_image_id": image_id,
        },
        "platform": {
            "os": "linux",
            "architecture": arch,
        },
        "same_content_required": True,
    },
    "runtime": {
        "networks": networks,
        "published_ports": ports,
        "mounts": [{
            "type": "bind",
            "source":
                "/home/james/docker/data/monitoring/blackbox/blackbox.yml",
            "destination":
                "/etc/blackbox_exporter/config.yml",
            "rw": False,
            "source_kind": "file",
            "sha256": config_sha,
        }],
        "user": "",
        "privileged": False,
        "readonly_rootfs": False,
        "restart_policy": "unless-stopped",
        "devices_allowed": False,
        "docker_socket_allowed": False,
        "compose_execution": {
            "no_deps": True,
            "no_build": True,
            "pull": "never",
            "force_recreate": True,
        },
    },
    "health": health,
    "protection": {
        "containers": protection,
        "compare": [
            "container_id",
            "restart_count",
        ],
        "all_other_containers_unchanged": True,
    },
    "execution": {
        "human_approval_required": True,
        "post_approval_reinspection_required": True,
        "one_shot_required": True,
        "target_must_be_local_before_arm": True,
        "deployment_pull_allowed": False,
        "rollback_required": True,
        "rollback_ref_type": "tagged-source-configuration",
        "normalization_kind": "tag-to-immutable-same-content",
    },
}

with open(output, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2)
    handle.write("\n")
PY
}

expect_pass() {
    local file="$1"

    python3 "$VALIDATOR" \
        --schema "$SCHEMA" \
        "$file" >/dev/null ||
        fail "expected PASS: $file"
}

expect_fail() {
    local file="$1"

    if python3 "$VALIDATOR" \
        --schema "$SCHEMA" \
        "$file" >/dev/null 2>&1
    then
        fail "expected rejection: $file"
    fi
}

TS_ID="sha256:66a289aee116c17f2396de73f97328f55eb4bb8fc53d8842a171eddc54685445"
IDS_ID="sha256:e753ff9f3fc458d02cca5eddab5a77e1c175eee484a8925ac7d524f04366c2fc"

make_manifest \
    "TestServer" \
    "arm64" \
    "$TS_ID" \
    "http" \
    "$TMP/testserver.json"

make_manifest \
    "ids-01" \
    "amd64" \
    "$IDS_ID" \
    "container-http" \
    "$TMP/ids01.json"

expect_pass "$TMP/testserver.json"
echo "PASS: TestServer positive normalization contract"

expect_pass "$TMP/ids01.json"
echo "PASS: ids-01 positive normalization contract"

python3 - "$TMP/testserver.json" "$TMP/bad-same-content.json" <<'PY'
import json
import sys

source, output = sys.argv[1:]
data = json.load(open(source))
data["image"]["target"]["local_image_id"] = (
    "sha256:" + ("0" * 64)
)
json.dump(data, open(output, "w"), indent=2)
PY

expect_fail "$TMP/bad-same-content.json"
echo "PASS: different target content rejected"

python3 - "$TMP/testserver.json" "$TMP/bad-rollback.json" <<'PY'
import json
import sys

source, output = sys.argv[1:]
data = json.load(open(source))
data["image"]["rollback"]["configured_image"] = (
    "prom/blackbox-exporter:v0.27.0"
)
json.dump(data, open(output, "w"), indent=2)
PY

expect_fail "$TMP/bad-rollback.json"
echo "PASS: non-source rollback tag rejected"

python3 - "$TMP/testserver.json" "$TMP/bad-target.json" <<'PY'
import json
import sys

source, output = sys.argv[1:]
data = json.load(open(source))
data["image"]["target"]["configured_image"] = (
    "prom/blackbox-exporter:v0.28.0"
)
json.dump(data, open(output, "w"), indent=2)
PY

expect_fail "$TMP/bad-target.json"
echo "PASS: mutable target rejected"

python3 - "$TMP/ids01.json" "$TMP/bad-health-network.json" <<'PY'
import json
import sys

source, output = sys.argv[1:]
data = json.load(open(source))
data["health"]["network"] = "not-reviewed"
json.dump(data, open(output, "w"), indent=2)
PY

expect_fail "$TMP/bad-health-network.json"
echo "PASS: unreviewed container-http network rejected"

python3 - "$TMP/testserver.json" "$TMP/bad-pull.json" <<'PY'
import json
import sys

source, output = sys.argv[1:]
data = json.load(open(source))
data["runtime"]["compose_execution"]["pull"] = "always"
json.dump(data, open(output, "w"), indent=2)
PY

expect_fail "$TMP/bad-pull.json"
echo "PASS: deploy-time pull rejected"

python3 - "$TMP/testserver.json" "$TMP/bad-approval.json" <<'PY'
import json
import sys

source, output = sys.argv[1:]
data = json.load(open(source))
data["execution"]["human_approval_required"] = False
json.dump(data, open(output, "w"), indent=2)
PY

expect_fail "$TMP/bad-approval.json"
echo "PASS: missing human approval rejected"

echo "PASS: image-reference normalization framework regression"
