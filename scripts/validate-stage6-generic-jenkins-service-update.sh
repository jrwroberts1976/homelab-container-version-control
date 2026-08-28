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

printf '\n===== PATCH HYGIENE =====\n'
git diff --check
printf 'PASS: git diff --check\n'

printf '\n===== RESULT =====\n'
printf 'PASS: Stage 6 generic Jenkins service-update source validation completed\n'
printf 'NO LIVE STAGE 6 FILES CHANGED\n'
printf 'NO ONE-SHOT AUTHORITY ARMED\n'
printf 'NO CONTAINER DEPLOYMENT PERFORMED\n'
