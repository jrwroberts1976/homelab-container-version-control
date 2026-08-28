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

echo "===== STAGE 6 GENERIC SERVICE DISPATCH SOURCE VALIDATION ====="

echo
echo_section() {
    printf '\n===== %s =====\n' "$1"
}

echo_section "SHELL SYNTAX"
bash -n \
    ops/testserver/homelab-stage6-inspector-ssh \
    ops/testserver/homelab-stage6-executor-ssh
printf 'PASS: forced-command wrapper shell syntax\n'

echo_section "PYTHON SYNTAX"
python3 - <<'PY'
import ast
from pathlib import Path

paths = [
    Path("scripts/validate-stage6-inspector-transport.py"),
    Path("scripts/validate-stage6-executor-activation.py"),
    Path("scripts/validate-stage6-execution-boundary.py"),
    Path("scripts/validate-stage6-service-manifest.py"),
]

for path in paths:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print(f"PASS: {path}")
PY

echo_section "NO SERVICE HARD-CODING"
if grep -Eiq '\b(dashy|prometheus)\b' \
    ops/testserver/homelab-stage6-inspector-ssh \
    ops/testserver/homelab-stage6-executor-ssh \
    ops/testserver/homelab-stage6-inspector-sudoers \
    ops/testserver/homelab-stage6-executor-sudoers; then
    fail "transport still hard-codes an onboarded service"
fi
printf 'PASS: wrappers and sudoers are service-agnostic\n'

echo_section "INSPECTOR TRANSPORT GUARD"
python3 scripts/validate-stage6-inspector-transport.py \
    ops/testserver/homelab-stage6-inspector-ssh \
    ops/testserver/homelab-stage6-inspector-sudoers \
    ops/testserver/homelab-stage6-inspector-authorized-key.template

echo_section "EXECUTOR ACTIVATION GUARD"
python3 scripts/validate-stage6-executor-activation.py \
    ops/testserver/homelab-stage6-executor-sudoers \
    ops/testserver/homelab-stage6-executor-authorized-key.template \
    ops/testserver/homelab-stage6-executor-ssh

echo_section "EXECUTION BOUNDARY GUARD"
python3 scripts/validate-stage6-execution-boundary.py \
    ops/testserver/homelab-stage6-transition \
    ops/testserver/homelab-stage6-execute \
    ops/testserver/homelab-stage6-executor-ssh

echo_section "SERVICE MANIFESTS"
for manifest in \
    config/services/dashy-4.6.0.json \
    config/services/prometheus-3.13.2.json
do
    python3 scripts/validate-stage6-service-manifest.py \
        "$manifest" \
        --schema config/service-update-manifest.schema.json
    printf 'PASS: %s\n' "$manifest"
done

echo_section "SUDOERS REGEX SYNTAX"
command -v visudo >/dev/null 2>&1 || fail "visudo unavailable"
visudo -cf ops/testserver/homelab-stage6-inspector-sudoers
visudo -cf ops/testserver/homelab-stage6-executor-sudoers
printf 'PASS: sudoers argument-regex syntax\n'

echo_section "PATCH HYGIENE"
git diff --check
printf 'PASS: git diff --check\n'

echo_section "RESULT"
printf 'PASS: Stage 6 generic service dispatch source validation completed\n'
printf 'NO HOST FILES CHANGED\n'
printf 'NO ONE-SHOT AUTHORITY ARMED\n'
printf 'NO CONTAINER DEPLOYMENT PERFORMED\n'
