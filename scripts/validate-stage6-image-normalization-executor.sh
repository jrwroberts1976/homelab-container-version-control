#!/bin/bash
set -u
set -o pipefail

ROOT="$(
    cd "$(dirname "$0")/.." &&
    pwd
)"

EXECUTOR="$ROOT/ops/testserver/homelab-stage6-normalization-execute"

fail() {
    echo "FAIL: $1"
    exit 2
}

[ -f "$EXECUTOR" ] ||
    fail "normalization executor missing"

bash -n "$EXECUTOR" ||
    fail "normalization executor shell syntax invalid"

for REQUIRED in \
    'normalization executor requires root' \
    'normalization executor is not running from reviewed installed path' \
    'normalization approval state invalid' \
    'approval zero-drift baseline hash mismatch' \
    'post-approval normalization inspection failed' \
    'post-approval zero-drift baseline mismatch' \
    'verify_approved_runtime_identity' \
    'normalization ID is already consumed' \
    'mark_consumed' \
    'Compose recreate failed; normalization remains consumed' \
    '--no-deps' \
    '--no-build' \
    '--pull never' \
    '--force-recreate' \
    'unrelated container state changed' \
    'target did not satisfy health contract before timeout' \
    'rollback is not exact tagged source configuration' \
    'container-http network is not reviewed' \
    'image_pulled:false' \
    'approval_remains_present:true'
do
    grep -Fq -- "$REQUIRED" "$EXECUTOR" ||
        fail "required executor safety gate missing: $REQUIRED"
done

echo "PASS: required execution safety gates present"

if grep -Eiq \
    '^[[:space:]]*docker[[:space:]]+(pull|rmi|rm|stop|start|restart|kill|create|run|tag)([[:space:]]|$)' \
    "$EXECUTOR"
then
    fail "unreviewed direct Docker mutation command detected"
fi

if grep -Eiq \
    'docker[[:space:]]+compose.*[[:space:]](down|restart|stop|start|rm|pull|build)([[:space:]]|$)' \
    "$EXECUTOR"
then
    fail "unreviewed Compose mutation command detected"
fi

if grep -Eiq \
    '(^|[[:space:]])(ssh|scp|rsync)([[:space:]]|$)' \
    "$EXECUTOR"
then
    fail "executor contains remote execution surface"
fi

if grep -Eiq \
    '^[[:space:]]*git[[:space:]].*[[:space:]](checkout|switch|reset|clean|commit|merge|rebase|cherry-pick|revert)([[:space:]]|$)' \
    "$EXECUTOR"
then
    fail "executor contains Git mutation command"
fi

echo "PASS: mutation surface restricted to reviewed Compose recreate"

COMPOSE_UP_COUNT="$(
    grep -Ec \
        '^[[:space:]]*up -d \\$' \
        "$EXECUTOR"
)"

[ "$COMPOSE_UP_COUNT" -eq 1 ] ||
    fail "expected exactly one Compose up mutation template"

echo "PASS: exactly one Compose recreate template"

python3 - "$EXECUTOR" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text()

def body(name, next_name):
    start = text.index(f"{name}() {{")
    end = text.index(f"\n{next_name}() {{", start)
    return text[start:end]

normalize = body("normalize", "rollback")

required_order = [
    "verify_git_authority",
    "verify_compose_images",
    "verify_local_images",
    "run_postapproval_reinspection",
    "verify_runtime_shape",
    "verify_approved_runtime_identity",
    "build_container_state",
    "mark_consumed",
    "compose_recreate",
    "wait_for_health",
    "verify_unrelated_unchanged",
]

positions = []
for token in required_order:
    pos = normalize.find(token)
    if pos < 0:
        raise SystemExit(f"normalize missing ordered gate: {token}")
    positions.append(pos)

if positions != sorted(positions):
    raise SystemExit(
        "normalize safety gates are not in required order"
    )

rollback = text[text.index("rollback() {"):]

for token in [
    "require_consumed",
    'verify_runtime_shape \\\n        "$TARGET_LOCAL_ID" \\\n        "$TARGET_REF"',
    'compose_recreate \\\n        "$ROLLBACK_REF"',
    'verify_runtime_shape \\\n        "$ROLLBACK_LOCAL_ID" \\\n        "$ROLLBACK_REF"',
    "wait_for_health",
    "verify_unrelated_unchanged",
]:
    if token not in rollback:
        raise SystemExit(f"rollback gate missing: {token}")

print("PASS: normalize and rollback gate ordering verified")
PY

echo "PASS: consumed marker precedes mutation"

grep -Fq \
    'STATE_ROOT="/var/lib/homelab-stage6/image-normalization-state"' \
    "$EXECUTOR" ||
    fail "fixed normalization state root missing"

grep -Fq \
    'APPROVAL_FILE="${SERVICE_STATE_DIR}/approval.json"' \
    "$EXECUTOR" ||
    fail "fixed approval state path missing"

grep -Fq \
    'CONSUMED_FILE="${SERVICE_STATE_DIR}/${NORMALIZATION_ID}.consumed"' \
    "$EXECUTOR" ||
    fail "fixed consumed state path missing"

echo "PASS: fixed approval/consumed state paths"

echo "PASS: normalization executor source regression"
