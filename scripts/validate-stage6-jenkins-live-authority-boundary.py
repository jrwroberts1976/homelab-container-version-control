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
    "STAGE6_FRAMEWORK_BASE_COMMIT = "
    "'3eaaf9b3698d6db0aa49d01f33ae68b749a78388'",
    "stage('Live authority gate')",
    "credentialsId: env.STAGE6_INSPECTOR_CREDENTIAL",
    '"authority $STAGE6_SERVICE"',
    "stage6-live-authority.json",
    "a.artifact != 'stage6-live-authority'",
    "a.result != 'live-authority-inspected'",
    "a.security?.root_owned != true",
    "a.security?.non_symlink != true",
    "a.security?.not_group_or_other_writable != true",
    "a.manifest_sha256 !=",
    "STAGE6_AUTHORITY_INSPECTOR_SOURCE_SHA256",
    "STAGE6_CANDIDATE_ACQUIRE_SOURCE_SHA256",
    "STAGE6_VALIDATOR_SOURCE_SHA256",
    "STAGE6_INSPECTOR_SOURCE_SHA256",
    "STAGE6_ACQUIRER_WRAPPER_SOURCE_SHA256",
    "STAGE6_INSPECTOR_WRAPPER_SOURCE_SHA256",
    "python3 scripts/validate-stage6-live-authority-boundary.py",
    "python3 scripts/validate-stage6-jenkins-live-authority-boundary.py",
]

for needle in required:
    if needle not in text:
        fail(
            "required Jenkins live-authority "
            f"invariant missing: {needle}"
        )


source_pos = text.find(
    "stage('Source and host-key preflight')"
)
authority_pos = text.find(
    "stage('Live authority gate')"
)
acquire_pos = text.find(
    "stage('Candidate acquisition')"
)
inspect_pos = text.find(
    "stage('Pre-approval inspection')"
)
approval_pos = text.find(
    "stage('Human approval')"
)

positions = [
    source_pos,
    authority_pos,
    acquire_pos,
    inspect_pos,
    approval_pos,
]

if any(pos < 0 for pos in positions):
    fail(
        "one or more Stage 6 authority/order "
        "stages are missing"
    )

if not (
    source_pos
    < authority_pos
    < acquire_pos
    < inspect_pos
    < approval_pos
):
    fail(
        "Stage 6 live-authority gate is not "
        "before candidate acquisition"
    )


before_authority = text[
    source_pos:authority_pos
]

for forbidden in [
    "credentialsId: env.STAGE6_ACQUIRER_CREDENTIAL",
    '"acquire $STAGE6_SERVICE"',
]:
    if forbidden in before_authority:
        fail(
            "candidate acquisition is reachable "
            "before live-authority PASS: "
            f"{forbidden}"
        )


authority_stage = text[
    authority_pos:acquire_pos
]

for required_authority in [
    "credentialsId: env.STAGE6_INSPECTOR_CREDENTIAL",
    '"authority $STAGE6_SERVICE"',
    "STAGE6_MANIFEST_SHA256",
    "STAGE6_AUTHORITY_INSPECTOR_SOURCE_SHA256",
    "STAGE6_CANDIDATE_ACQUIRE_SOURCE_SHA256",
    "STAGE6_VALIDATOR_SOURCE_SHA256",
    "STAGE6_INSPECTOR_SOURCE_SHA256",
    "STAGE6_ACQUIRER_WRAPPER_SOURCE_SHA256",
    "STAGE6_INSPECTOR_WRAPPER_SOURCE_SHA256",
]:
    if required_authority not in authority_stage:
        fail(
            "live-authority stage invariant missing: "
            f"{required_authority}"
        )


for forbidden in [
    "STAGE6_ACQUIRER_CREDENTIAL",
    "homelab-stage6-acquirer",
    '"acquire $STAGE6_SERVICE"',
    "STAGE6_EXECUTOR_CREDENTIAL",
    "homelab-stage6-executor",
]:
    if forbidden in authority_stage:
        fail(
            "live-authority stage crosses credential "
            f"boundary: {forbidden}"
        )


source_preflight = text[
    source_pos:authority_pos
]

for source_required in [
    "ops/testserver/homelab-stage6-authority-inspect",
    "scripts/validate-stage6-live-authority-boundary.py",
    "scripts/validate-stage6-jenkins-live-authority-boundary.py",
]:
    if source_required not in source_preflight:
        fail(
            "live-authority dependency is not "
            f"source-preflighted: {source_required}"
        )


acquisition_stage = text[
    acquire_pos:inspect_pos
]

if (
    "credentialsId: env.STAGE6_ACQUIRER_CREDENTIAL"
    not in acquisition_stage
):
    fail(
        "candidate acquisition no longer binds "
        "the reviewed acquirer credential"
    )


print(
    "PASS: Stage 6 Jenkins live-authority/"
    "credential-order boundary"
)
