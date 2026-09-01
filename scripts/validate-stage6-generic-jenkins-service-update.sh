#!/bin/bash
set -euo pipefail

PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 2
}

echo "===== STAGE 6 GENERIC JENKINS SERVICE UPDATE SOURCE VALIDATION ====="

printf '\n===== PYTHON SYNTAX =====\n'
python3 - <<'PY'
import ast
from pathlib import Path

for path in (
    Path("scripts/validate-stage6-generic-jenkins-pipeline.py"),
    Path("scripts/validate-stage6-service-manifest.py"),
):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print(f"PASS: {path}")
PY

printf '\n===== GENERIC PIPELINE GUARD =====\n'
python3 scripts/validate-stage6-generic-jenkins-pipeline.py \
    Jenkinsfile.stage6-service-update

printf '\n===== REVIEWED MANIFESTS =====\n'
for manifest in config/services/*.json; do
    [ -f "$manifest" ] || continue
    python3 scripts/validate-stage6-service-manifest.py \
        "$manifest" \
        --schema config/service-update-manifest.schema.json
    printf 'PASS: %s\n' "$manifest"
done

printf '\n===== PIPELINE SERVICE AGNOSTIC CHECK =====\n'
if grep -Eiq '\b(dashy|prometheus)\b' Jenkinsfile.stage6-service-update; then
    fail "generic Jenkins pipeline contains a service-specific name"
fi
printf 'PASS: no onboarded service is hard-coded in the generic pipeline\n'

printf '\n===== RUNTIME JSON CANONICALIZATION =====\n'

canonical_count="$(
    grep -c 'jq -S -c' \
        ops/testserver/homelab-stage6-inspect ||
    true
)"

[ "$canonical_count" -ge 4 ] ||
    fail "generic inspector does not canonicalise all runtime JSON comparisons"

executor_canonical_count="$(
    grep -c 'jq -S -c' \
        ops/testserver/homelab-stage6-execute ||
    true
)"

[ "$executor_canonical_count" -ge 4 ] ||
    fail "generic executor does not canonicalise all runtime JSON comparisons"

expected_ports='[
  {
    "container_port": 9090,
    "host_ip": "192.168.2.220",
    "host_port": 9090,
    "protocol": "tcp"
  }
]'

actual_ports='[
  {
    "host_ip": "192.168.2.220",
    "host_port": 9090,
    "container_port": 9090,
    "protocol": "tcp"
  }
]'

expected_canonical="$(
    jq -S -c . <<<"$expected_ports"
)"

actual_canonical="$(
    jq -S -c . <<<"$actual_ports"
)"

[ "$expected_canonical" = "$actual_canonical" ] ||
    fail "canonical JSON regression test failed"

printf 'PASS: JSON object key order does not create false runtime drift\n'

printf '\n===== READ-ONLY DOCKER SOCKET CONTRACT =====\n'

python3 - <<'PYTEST'
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

base = json.loads(
    Path("config/services/dashy-4.6.0.json").read_text(
        encoding="utf-8"
    )
)

socket_mount = {
    "type": "bind",
    "source": "/var/run/docker.sock",
    "destination": "/var/run/docker.sock",
    "rw": False,
    "source_kind": "socket",
    "sha256": None,
}


def validate_case(name, manifest, should_pass):
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as handle:
        json.dump(manifest, handle)
        handle.write("\n")
        filename = Path(handle.name)

    try:
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/validate-stage6-service-manifest.py",
                str(filename),
                "--schema",
                "config/service-update-manifest.schema.json",
            ],
            text=True,
            capture_output=True,
        )

        actual_pass = proc.returncode == 0

        if actual_pass != should_pass:
            print(f"FAIL: {name}")
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(2)

        result = "PASS" if should_pass else "REJECTED"
        print(f"PASS: {name} -> {result}")

    finally:
        filename.unlink(missing_ok=True)


safe = copy.deepcopy(base)
safe["service"]["risk_class"] = "medium"
safe["runtime"]["docker_socket_allowed"] = True
safe["runtime"]["mounts"].append(
    copy.deepcopy(socket_mount)
)
validate_case(
    "exact medium-risk read-only Docker socket",
    safe,
    True,
)

low_risk = copy.deepcopy(safe)
low_risk["service"]["risk_class"] = "low"
validate_case(
    "low-risk Docker socket",
    low_risk,
    False,
)

writable = copy.deepcopy(safe)
writable["runtime"]["mounts"][-1]["rw"] = True
validate_case(
    "writable Docker socket",
    writable,
    False,
)

wrong_source = copy.deepcopy(safe)
wrong_source["runtime"]["mounts"][-1][
    "source"
] = "/tmp/docker.sock"
validate_case(
    "alternate Docker socket source",
    wrong_source,
    False,
)

wrong_destination = copy.deepcopy(safe)
wrong_destination["runtime"]["mounts"][-1][
    "destination"
] = "/tmp/docker.sock"
validate_case(
    "alternate Docker socket destination",
    wrong_destination,
    False,
)

wrong_kind = copy.deepcopy(safe)
wrong_kind["runtime"]["mounts"][-1][
    "source_kind"
] = "file"
wrong_kind["runtime"]["mounts"][-1][
    "sha256"
] = "0" * 64
validate_case(
    "Docker socket declared as file",
    wrong_kind,
    False,
)

disabled = copy.deepcopy(safe)
disabled["runtime"]["docker_socket_allowed"] = False
validate_case(
    "socket present while policy disabled",
    disabled,
    False,
)

missing = copy.deepcopy(base)
missing["service"]["risk_class"] = "medium"
missing["runtime"]["docker_socket_allowed"] = True
validate_case(
    "socket policy enabled without mount",
    missing,
    False,
)

duplicate = copy.deepcopy(safe)
duplicate["runtime"]["mounts"].append(
    copy.deepcopy(socket_mount)
)
duplicate["runtime"]["mounts"][-1][
    "destination"
] = "/tmp/second-docker.sock"
validate_case(
    "multiple Docker socket mounts",
    duplicate,
    False,
)

print("PASS: Docker socket positive/negative contract complete")
PYTEST

printf '\n===== REVIEWED AUDIO DEVICE CONTRACT =====\n'

python3 - <<'PYDEVICE'
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

base = json.loads(
    Path("config/services/dashy-4.6.0.json").read_text(
        encoding="utf-8"
    )
)

audio_device = {
    "source": "/dev/snd",
    "destination": "/dev/snd",
    "permissions": "rwm",
}


def validate_case(name, manifest, should_pass):
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as handle:
        json.dump(manifest, handle)
        handle.write("\n")
        filename = Path(handle.name)

    try:
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/validate-stage6-service-manifest.py",
                str(filename),
                "--schema",
                "config/service-update-manifest.schema.json",
            ],
            text=True,
            capture_output=True,
        )

        actual_pass = proc.returncode == 0

        if actual_pass != should_pass:
            print(f"FAIL: {name}")
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(2)

        result = "PASS" if should_pass else "REJECTED"
        print(f"PASS: {name} -> {result}")

    finally:
        filename.unlink(missing_ok=True)


safe = copy.deepcopy(base)
safe["service"]["risk_class"] = "medium"
safe["runtime"]["devices_allowed"] = True
safe["runtime"]["devices"] = [
    copy.deepcopy(audio_device)
]
safe["runtime"]["docker_socket_allowed"] = False

validate_case(
    "exact medium-risk /dev/snd audio device",
    safe,
    True,
)

low_risk = copy.deepcopy(safe)
low_risk["service"]["risk_class"] = "low"
validate_case(
    "low-risk audio device",
    low_risk,
    False,
)

wrong_source = copy.deepcopy(safe)
wrong_source["runtime"]["devices"][0]["source"] = "/dev/video0"
validate_case(
    "alternate audio device source",
    wrong_source,
    False,
)

wrong_destination = copy.deepcopy(safe)
wrong_destination["runtime"]["devices"][0][
    "destination"
] = "/dev/audio"
validate_case(
    "alternate audio device destination",
    wrong_destination,
    False,
)

wrong_permissions = copy.deepcopy(safe)
wrong_permissions["runtime"]["devices"][0][
    "permissions"
] = "rw"
validate_case(
    "alternate audio device permissions",
    wrong_permissions,
    False,
)

disabled = copy.deepcopy(safe)
disabled["runtime"]["devices_allowed"] = False
validate_case(
    "device mapping present while policy disabled",
    disabled,
    False,
)

missing = copy.deepcopy(base)
missing["service"]["risk_class"] = "medium"
missing["runtime"]["devices_allowed"] = True
missing["runtime"]["devices"] = []
missing["runtime"]["docker_socket_allowed"] = False
validate_case(
    "audio device policy enabled without mapping",
    missing,
    False,
)

socket_combo = copy.deepcopy(safe)
socket_combo["runtime"]["docker_socket_allowed"] = True
socket_combo["runtime"]["mounts"].append(
    {
        "type": "bind",
        "source": "/var/run/docker.sock",
        "destination": "/var/run/docker.sock",
        "rw": False,
        "source_kind": "socket",
        "sha256": None,
    }
)
validate_case(
    "audio device combined with Docker socket",
    socket_combo,
    False,
)

print("PASS: reviewed audio device positive/negative contract complete")
PYDEVICE

for helper in \
    ops/testserver/homelab-stage6-inspect \
    ops/testserver/homelab-stage6-execute
do
    grep -F \
        'target Docker socket mount is not the exact reviewed read-only socket' \
        "$helper" >/dev/null ||
        fail "exact runtime socket gate missing: $helper"

    grep -F \
        '[ -S "$source" ]' \
        "$helper" >/dev/null ||
        fail "Unix socket type gate missing: $helper"

    grep -F \
        'expected_devices_allowed' \
        "$helper" >/dev/null ||
        fail "audio device policy gate missing: $helper"

    grep -F \
        'source: .PathOnHost' \
        "$helper" >/dev/null ||
        fail "audio device host-path runtime gate missing: $helper"

    grep -F \
        'destination: .PathInContainer' \
        "$helper" >/dev/null ||
        fail "audio device container-path runtime gate missing: $helper"

    grep -F \
        'permissions: .CgroupPermissions' \
        "$helper" >/dev/null ||
        fail "audio device permission runtime gate missing: $helper"

    grep -F \
        'target device mapping does not exactly match reviewed audio device contract' \
        "$helper" >/dev/null ||
        fail "exact audio device runtime comparison missing: $helper"
done

grep -F \
    'config/service-update-manifest.schema.json \' \
    Jenkinsfile.stage6-service-update >/dev/null ||
    fail "schema is absent from Jenkins framework drift gate"

printf 'PASS: runtime helpers and Jenkins schema-drift protection present\n'

printf '\n===== PATCH HYGIENE =====\n'
git diff --check
printf 'PASS: git diff --check\n'

printf '\n===== RESULT =====\n'
printf 'PASS: Stage 6 generic Jenkins service-update source validation completed\n'
printf 'NO LIVE STAGE 6 FILES CHANGED\n'
printf 'NO ONE-SHOT AUTHORITY ARMED\n'
printf 'NO CONTAINER DEPLOYMENT PERFORMED\n'
