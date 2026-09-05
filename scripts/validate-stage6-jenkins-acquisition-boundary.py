#!/usr/bin/env python3

from pathlib import Path
import sys


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


path = Path("Jenkinsfile.stage6-service-update")

if not path.is_file():
    fail("Jenkinsfile.stage6-service-update missing")

text = path.read_text(encoding="utf-8")

required = [
    "stage('Select reviewed manifest')",
    "name: 'STAGE6_REVIEWED_SELECTION'",
    "scripts/stage6-reviewed-manifest-selector.py",
    "current-estate-reviewed-choices-derived",
    "env.STAGE6_MANIFEST = manifestName",
    "acquirerCredential: 'homelab-stage6-testserver-acquirer'",
    "env.STAGE6_ACQUIRER_CREDENTIAL = "
    "(route.acquirerCredential ?: '').toString()",
    "stage('Candidate acquisition')",
    "credentialsId: env.STAGE6_ACQUIRER_CREDENTIAL",
    '"acquire $STAGE6_SERVICE"',
    "a.artifact != 'stage6-candidate-acquisition'",
    "a.result != 'acquired-and-verified'",
    "a.container_mutation_performed != false",
    "UPDATE host has no reviewed Stage 6 candidate-acquirer route",
    "candidate-acquisition-output.txt",
    "expected exactly one acquisition JSON object",
    "python3 scripts/validate-stage6-candidate-acquisition.py",
    "python3 scripts/validate-stage6-acquirer-boundary.py",
    "python3 scripts/validate-stage6-jenkins-acquisition-boundary.py",
]

for needle in required:
    if needle not in text:
        fail(f"required acquisition pipeline invariant missing: {needle}")


selector_path = Path(
    "scripts/stage6-reviewed-manifest-selector.py"
)

if not selector_path.is_file():
    fail(
        "Stage 6 reviewed-manifest selector source missing"
    )

selector_text = selector_path.read_text(
    encoding="utf-8"
)

selector_required = [
    "config/estate-updater-catalog.json",
    'action not in {"UPDATE", "VERIFY_CLOSED"}',
    'if action == "UPDATE":',
    "current == rollback",
    "current == candidate",
    "current-estate-reviewed-choices-derived",
]

for needle in selector_required:
    if needle not in selector_text:
        fail(
            "required current-estate selector invariant "
            f"missing: {needle}"
        )


selector_invocation = (
    'scripts/stage6-reviewed-manifest-selector.py \\\n'
    '              "$STAGE6_ACTION"'
)

if selector_invocation not in text:
    fail(
        "Jenkins does not pass STAGE6_ACTION "
        "to the reviewed-manifest selector"
    )


preflight_selector_invocation = (
    'python3 scripts/stage6-reviewed-manifest-selector.py \\\n'
    '            "$STAGE6_ACTION" \\\n'
    '            >/dev/null'
)

if preflight_selector_invocation not in text:
    fail(
        "Stage 6 source preflight does not pass "
        "STAGE6_ACTION to the reviewed-manifest selector"
    )


if "==~ /" in text:
    fail(
        "slashy Groovy regex remains in Jenkinsfile; "
        "use quoted regex strings for Declarative/CPS compatibility"
    )


for forbidden in [
    "name: 'STAGE6_MANIFEST'",
    "params.STAGE6_MANIFEST",
    "STAGE6_MANIFEST_PREPARED",
    "stage('Prepare missing manifest')",
    "stage('Manifest review required')",
    "prepare-stage6-service-manifest.py",
]:
    if forbidden in text:
        fail(
            f"legacy free-text manifest selector remains: {forbidden}"
        )


checkout_pos = text.find("stage('Checkout')")
selector_pos = text.find("stage('Select reviewed manifest')")
load_pos = text.find("stage('Load reviewed manifest')")
source_pos = text.find("stage('Source and host-key preflight')")
acquire_pos = text.find("stage('Candidate acquisition')")
inspect_pos = text.find("stage('Pre-approval inspection')")
approval_pos = text.find("stage('Human approval')")
reinspect_pos = text.find("stage('Re-inspect after approval')")
executor_pos = text.find("stage('Executor preflight after approval')")

positions = [
    checkout_pos,
    selector_pos,
    load_pos,
    source_pos,
    acquire_pos,
    inspect_pos,
    approval_pos,
    reinspect_pos,
    executor_pos,
]

if any(pos < 0 for pos in positions):
    fail("one or more required Stage 6 stages are missing")

if not (
    checkout_pos
    < selector_pos
    < load_pos
    < source_pos
    < acquire_pos
    < inspect_pos
    < approval_pos
    < reinspect_pos
    < executor_pos
):
    fail(
        "Stage 6 selector/acquisition/approval/"
        "executor ordering is unsafe"
    )


preapproval_execution = text[acquire_pos:approval_pos]

if "STAGE6_EXECUTOR_CREDENTIAL" in preapproval_execution:
    fail("executor credential referenced before human approval")

if "homelab-stage6-executor" in preapproval_execution:
    fail("executor identity referenced before human approval")


if (
    "ops/testserver/homelab-stage6-candidate-acquire"
    not in text[source_pos:acquire_pos]
):
    fail("candidate acquisition helper is not source-preflighted")

if (
    "scripts/validate-stage6-acquirer-boundary.py"
    not in text[source_pos:acquire_pos]
):
    fail("acquirer boundary guard is not source-preflighted")


print(
    "PASS: Stage 6 Jenkins acquisition/approval/executor boundary"
)
