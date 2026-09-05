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


source_pos = text.find("stage('Source and host-key preflight')")
acquire_pos = text.find("stage('Candidate acquisition')")
inspect_pos = text.find("stage('Pre-approval inspection')")
approval_pos = text.find("stage('Human approval')")
reinspect_pos = text.find("stage('Re-inspect after approval')")
executor_pos = text.find("stage('Executor preflight after approval')")

positions = [
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
    source_pos
    < acquire_pos
    < inspect_pos
    < approval_pos
    < reinspect_pos
    < executor_pos
):
    fail("Stage 6 acquisition/approval/executor ordering is unsafe")


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
