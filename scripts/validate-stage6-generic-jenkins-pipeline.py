#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def require_order(text: str, needles: list[str], label: str) -> None:
    positions = []
    for needle in needles:
        pos = text.find(needle)
        require(pos >= 0, f"{label} token missing: {needle}")
        positions.append(pos)
    require(positions == sorted(positions), f"{label} ordering is incorrect")


def count(text: str, needle: str) -> int:
    return text.count(needle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pipeline", type=Path)
    args = parser.parse_args()

    text = args.pipeline.read_text(encoding="utf-8")
    lowered = text.lower()

    require("parameters {" in text, "pipeline parameters block missing")
    require("name: 'STAGE6_MANIFEST'" in text, "manifest selector parameter missing")
    require("defaultValue: ''" in text, "manifest selector must not default to a service")
    require(
        "manifestName ==~ /^[a-z0-9][a-z0-9.-]*\\.json$/" in text,
        "manifest filename allow-list regex missing",
    )
    require(
        "service ==~ /^[a-z0-9][a-z0-9-]*$/" in text,
        "service identifier allow-list regex missing",
    )
    require(
        'def manifestPath = "config/services/${manifestName}"' in text,
        "manifest path must remain under fixed config/services root",
    )
    require(
        'python3 scripts/validate-stage6-service-manifest.py' in text
        and '--schema config/service-update-manifest.schema.json' in text,
        "reviewed manifest validator/schema gate missing",
    )

    for literal in ("dashy", "prometheus", "lissy93/", "prom/prometheus"):
        require(literal not in lowered, f"service/image hard-coding present: {literal}")

    require("@sha256:" not in text, "pipeline must not hard-code immutable image references")

    forbidden = [
        "docker ",
        "sudo ",
        "eval ",
        "bash -c",
        "sh -c",
        "curl ",
        "wget ",
        "scp ",
        "rsync ",
    ]
    for token in forbidden:
        require(token not in lowered, f"pipeline contains forbidden direct authority: {token.strip()}")

    required_manifest_derivations = [
        'env.STAGE6_SERVICE = service',
        'env.STAGE6_UPDATE_ID = "stage6-${service}-${candidateDigest.substring(7)}"',
        'env.STAGE6_AUTHORITY_COMMIT = m.authority?.revision?.toString()',
        'env.STAGE6_COMPOSE_SHA256 = m.authority?.compose_sha256?.toString()',
        'env.STAGE6_ROLLBACK_REF = rollback?.immutable_ref?.toString()',
        'env.STAGE6_ROLLBACK_IMAGE_ID = rollback?.local_image_id?.toString()',
        'env.STAGE6_CANDIDATE_REF = candidate?.immutable_ref?.toString()',
        'env.STAGE6_CANDIDATE_IMAGE_ID = candidate?.config_digest?.toString()',
        'env.STAGE6_HEALTH_RESULT = healthResult',
        'env.STAGE6_MANIFEST_SHA256 = sh(',
        'env.STAGE6_INSPECTOR_SOURCE_SHA256 = sh(',
    ]
    for token in required_manifest_derivations:
        require(token in text, f"manifest-derived pipeline value missing: {token}")

    required_stages = [
        "stage('Checkout')",
        "stage('Load reviewed manifest')",
        "stage('Source and host-key preflight')",
        "stage('Pre-approval inspection')",
        "stage('Assert pre-approval artifact')",
        "stage('Human approval')",
        "stage('Re-inspect after approval')",
        "stage('Assert zero drift after approval')",
        "stage('Executor preflight after approval')",
        "stage('Arm exact update')",
        "stage('Deploy exact candidate')",
        "stage('Rollback on deploy failure')",
        "stage('Disarm terminal state')",
        "stage('Final pipeline result')",
    ]
    require_order(text, required_stages, "pipeline stage")

    drift_pos = text.find("stage('Assert zero drift after approval')")
    first_executor_credential = text.find("credentialsId: 'homelab-stage6-testserver-executor'")
    require(drift_pos >= 0 and first_executor_credential > drift_pos, "executor credential appears before zero-drift gate")

    require(
        count(text, "credentialsId: 'homelab-stage6-testserver-inspector'") == 2,
        "pipeline must bind inspector credential exactly twice",
    )
    require(
        count(text, "credentialsId: 'homelab-stage6-testserver-executor'") == 5,
        "pipeline must bind executor credential exactly five times",
    )

    expected_remote = {
        '"inspect $STAGE6_SERVICE"': 2,
        '"arm $STAGE6_SERVICE"': 1,
        '"deploy $STAGE6_SERVICE"': 1,
        '"rollback $STAGE6_SERVICE"': 1,
        '"disarm $STAGE6_SERVICE"': 1,
    }
    for token, expected in expected_remote.items():
        require(count(text, token) == expected, f"remote command count mismatch for {token}")

    require(
        count(text, "scripts/stage6-normalize-executor-key.sh") == 7,
        "normalizer references must be two preflight checks plus five executor uses",
    )
    require(count(text, '-i "$NORMALIZED_EXECUTOR_KEY"') == 5, "all executor SSH calls must use normalized key")

    for raw in (
        "STAGE6_EXECUTOR_PING_KEY",
        "STAGE6_ARM_KEY",
        "STAGE6_DEPLOY_KEY",
        "STAGE6_ROLLBACK_KEY",
        "STAGE6_DISARM_KEY",
    ):
        require(f'-i "${raw}"' not in text, f"raw executor key passed directly to SSH: {raw}")

    require("submitter: 'james'" in text, "explicit human approver gate missing")
    require("submitterParameter: 'APPROVED_BY'" in text, "approval identity capture missing")
    require("env.STAGE6_APPROVED_BY != 'james'" in text, "approval identity assertion missing")
    require("timeout(time: 60, unit: 'MINUTES')" in text, "approval timeout missing")

    artifact_assertions = [
        "a.manifest_sha256 != env.STAGE6_MANIFEST_SHA256",
        "a.implementation?.inspector_sha256 != env.STAGE6_INSPECTOR_SOURCE_SHA256",
        "a.current?.configured_image != env.STAGE6_ROLLBACK_TAG",
        "a.runtime?.health_strategy != env.STAGE6_HEALTH_STRATEGY",
        "a.runtime?.health_result != env.STAGE6_HEALTH_RESULT",
        "if (before != after)",
        "a.health_result != env.STAGE6_HEALTH_RESULT",
        "a.unrelated_containers_unchanged != true",
        "a.deployment_authority_remains_armed != true",
        "a.deployment_authority != false",
    ]
    for token in artifact_assertions:
        require(token in text, f"artifact assertion missing: {token}")

    require("rc == 96 || rc == 97" in text, "pre-SSH deploy failure classification missing")
    require("Rollback must not be attempted" in text, "pre-SSH rollback prohibition missing")
    require("env.STAGE6_DEPLOY_RC != '96'" in text and "env.STAGE6_DEPLOY_RC != '97'" in text, "rollback exclusion for local credential failures missing")
    require("Execution remains armed/consumed for controlled manual recovery" in text, "failed rollback recovery boundary missing")

    require("archiveArtifacts(" in text, "artifact archival missing")
    require("artifacts: 'artifacts/stage6-*'" in text, "generic artifact archival pattern missing")

    print("PASS: Stage 6 generic manifest-driven Jenkins pipeline source guard")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
