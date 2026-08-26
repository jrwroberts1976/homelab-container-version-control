#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ALLOWED_PLANNER_RESULTS = {"same", "upgrade"}


def die(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except OSError as exc:
        die(f"cannot read JSON file {path}: {exc}")
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")


def repository_from_reference(reference):
    reference = reference.split("@", 1)[0]

    slash = reference.rfind("/")
    colon = reference.rfind(":")

    if colon > slash:
        reference = reference[:colon]

    if not reference:
        die("candidate image repository is empty")

    return reference


def trivy_version():
    proc = subprocess.run(
        ["trivy", "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if proc.returncode != 0:
        die(
            "unable to determine Trivy version"
            + (f": {proc.stderr.strip()}" if proc.stderr.strip() else "")
        )

    first_line = proc.stdout.splitlines()[0].strip()

    if first_line.startswith("Version:"):
        return first_line.split(":", 1)[1].strip()

    return first_line


def validate_plan(plan):
    if plan.get("mode") != "read-only":
        die("planner mode is not read-only")

    deployment = plan.get("deployment") or {}

    if deployment.get("allowed") is not False:
        die("planner does not explicitly disable deployment")

    if deployment.get("performed") is not False:
        die("planner reports deployment was performed")

    comparison = plan.get("comparison") or {}
    comparison_result = comparison.get("result")

    if comparison_result not in ALLOWED_PLANNER_RESULTS:
        die(
            "planner result is not eligible for security scanning: "
            f"{comparison_result!r}"
        )

    candidate = plan.get("candidate") or {}

    image = candidate.get("image")
    digest = candidate.get("index_digest")
    platform = candidate.get("platform") or {}

    if not isinstance(image, str) or not image:
        die("planner candidate image is missing")

    if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        die("planner candidate index digest is not a valid SHA-256 digest")

    os_name = platform.get("os")
    architecture = platform.get("architecture")

    if not os_name or not architecture:
        die("planner candidate platform is incomplete")

    if "@" in image:
        declared_digest = image.rsplit("@", 1)[1]

        if declared_digest != digest:
            die(
                "candidate image digest does not match planner "
                "candidate index digest"
            )

    repository = repository_from_reference(image)
    immutable_reference = f"{repository}@{digest}"

    return {
        "image": image,
        "digest": digest,
        "repository": repository,
        "immutable_reference": immutable_reference,
        "platform": f"{os_name}/{architecture}",
        "platform_object": platform,
        "comparison_result": comparison_result,
        "comparison_method": comparison.get("method"),
    }


def read_db_metadata(cache_dir):
    path = Path(cache_dir) / "db" / "metadata.json"

    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    return {
        "version": data.get("Version"),
        "updated_at": data.get("UpdatedAt"),
        "next_update": data.get("NextUpdate"),
        "downloaded_at": data.get("DownloadedAt"),
    }


def run_trivy(candidate, cache_dir):
    command = [
        "trivy",
        "image",
        "--image-src",
        "remote",
        "--platform",
        candidate["platform"],
        "--scanners",
        "vuln",
        "--severity",
        "HIGH,CRITICAL",
        "--format",
        "json",
        "--exit-code",
        "0",
        "--skip-version-check",
        "--cache-dir",
        str(cache_dir),
        candidate["immutable_reference"],
    ]

    proc = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if proc.returncode != 0:
        die(
            "Trivy remote scan failed"
            + (f": {proc.stderr.strip()}" if proc.stderr.strip() else "")
        )

    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        die(f"Trivy did not return valid JSON: {exc}")

    return report


def validate_report_identity(report, candidate):
    artifact_name = report.get("ArtifactName")

    if artifact_name != candidate["immutable_reference"]:
        die(
            "Trivy artifact identity mismatch: "
            f"expected {candidate['immutable_reference']}, "
            f"got {artifact_name!r}"
        )

    metadata = report.get("Metadata") or {}
    repo_digests = metadata.get("RepoDigests") or []

    if candidate["immutable_reference"] not in repo_digests:
        die(
            "Trivy report does not contain the expected immutable "
            "candidate RepoDigest"
        )

    return {
        "artifact_name": artifact_name,
        "artifact_type": report.get("ArtifactType"),
        "image_id": metadata.get("ImageID"),
        "repo_digests": repo_digests,
    }


def count_findings(report):
    critical = 0
    high = 0

    for result in report.get("Results") or []:
        for vulnerability in result.get("Vulnerabilities") or []:
            severity = vulnerability.get("Severity")

            if severity == "CRITICAL":
                critical += 1
            elif severity == "HIGH":
                high += 1

    return {
        "critical": critical,
        "high": high,
        "total": critical + high,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Stage 4 Trivy security gate for an immutable "
            "candidate image from plan-image-update.py."
        )
    )

    parser.add_argument(
        "--plan",
        required=True,
        help="candidate planner JSON file",
    )

    parser.add_argument(
        "--cache-dir",
        required=True,
        help="explicit Trivy cache directory",
    )

    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    plan = load_json(args.plan)
    candidate = validate_plan(plan)

    version = trivy_version()
    report = run_trivy(candidate, cache_dir)
    report_identity = validate_report_identity(report, candidate)
    findings = count_findings(report)

    gate_result = (
        "pass"
        if findings["total"] == 0
        else "security-blocked"
    )

    output = {
        "schema_version": 1,
        "mode": "read-only",
        "gate": "trivy-candidate-security",
        "candidate": {
            "image": candidate["image"],
            "immutable_reference": candidate["immutable_reference"],
            "digest": candidate["digest"],
            "platform": candidate["platform_object"],
        },
        "planner": {
            "result": candidate["comparison_result"],
            "method": candidate["comparison_method"],
        },
        "scanner": {
            "name": "trivy",
            "version": version,
            "image_source": "remote",
            "scanners": ["vuln"],
            "severities": ["HIGH", "CRITICAL"],
            "database": read_db_metadata(cache_dir),
        },
        "report_identity": report_identity,
        "findings": findings,
        "result": gate_result,
        "deployment": {
            "allowed": False,
            "performed": False,
        },
    }

    json.dump(output, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    raise SystemExit(0 if gate_result == "pass" else 1)


if __name__ == "__main__":
    main()
