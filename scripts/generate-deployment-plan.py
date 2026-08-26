#!/usr/bin/env python3

import argparse
import json
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OWNERSHIP_RESOLVER = PROJECT_ROOT / "scripts" / "resolve-service-ownership.sh"
IMAGE_PLANNER = PROJECT_ROOT / "scripts" / "plan-image-update.py"
SECURITY_GATE = PROJECT_ROOT / "scripts" / "validate-image-security.py"
SECRET_GATE = PROJECT_ROOT / "scripts" / "validate-secret-readiness.py"
PROVENANCE_GATE = PROJECT_ROOT / "scripts" / "validate-local-build-provenance.py"
SCHEMA_PATH = PROJECT_ROOT / "config" / "deployment-plan.schema.json"


def die(message, exit_code=2):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def run_json(command, accepted_codes=(0,)):
    proc = subprocess.run(
        [str(part) for part in command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    data = None

    if proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = None

    if proc.returncode not in accepted_codes:
        return proc.returncode, data

    if data is None:
        die(
            "read-only gate returned no valid JSON: "
            + Path(str(command[0])).name
        )

    return proc.returncode, data


def require_mapping(value, name):
    if not isinstance(value, dict):
        die(f"required object missing or invalid: {name}")
    return value


def require_string(value, name):
    if not isinstance(value, str) or not value:
        die(f"required string missing or invalid: {name}")
    return value


def deployment_disabled(data, name):
    deployment = require_mapping(
        data.get("deployment"),
        f"{name}.deployment",
    )

    if deployment.get("allowed") is not False:
        die(f"{name} unexpectedly permits deployment")

    if deployment.get("performed") is not False:
        die(f"{name} unexpectedly reports deployment performed")


def validate_read_only_gate(data, name):
    if data.get("mode") != "read-only":
        die(f"{name} is not read-only")

    deployment_disabled(data, name)


def null_runtime():
    return {
        "image": None,
        "image_id": None,
        "digest": None,
        "platform": None,
    }


def null_candidate():
    return {
        "image": None,
        "index_digest": None,
        "platform_digest": None,
        "platform": None,
    }


def platform(os_value, architecture):
    if not os_value or not architecture:
        return None

    return {
        "os": os_value,
        "architecture": architecture,
    }


def ownership_service(ownership):
    return {
        "container": require_string(
            ownership.get("container"),
            "ownership.container",
        ),
        "service": require_string(
            ownership.get("compose_service"),
            "ownership.compose_service",
        ),
        "host": socket.gethostname(),
        "authority": require_string(
            ownership.get("authority"),
            "ownership.authority",
        ),
        "repository": ownership.get("repository"),
        "image_type": require_string(
            ownership.get("image_type"),
            "ownership.image_type",
        ),
    }


def base_document(ownership):
    return {
        "schema_version": 1,
        "mode": "read-only",
        "artifact": "deployment-plan",
        "service": ownership_service(ownership),
        "authority": {
            "revision": None,
            "compose_files": [],
        },
        "runtime": null_runtime(),
        "candidate": null_candidate(),
        "gates": {
            "ownership": {
                "result": "pass",
            },
            "comparison": {
                "result": "not-applicable",
            },
            "architecture": {
                "result": "not-applicable",
            },
            "security": {
                "result": "not-applicable",
            },
            "secret_readiness": {
                "result": "not-applicable",
            },
            "local_build_provenance": {
                "result": "not-applicable",
            },
        },
        "decision": {
            "result": "blocked",
            "proposed_action": "manual-review",
            "reasons": [],
        },
        "deployment": {
            "allowed": False,
            "performed": False,
        },
    }


def run_secret_readiness(authority_root, service):
    rc, result = run_json(
        [
            SECRET_GATE,
            "--authority-root",
            authority_root,
            "--service",
            service,
        ],
        accepted_codes=(0, 1, 2),
    )

    if result is None:
        return rc, None

    validate_read_only_gate(
        result,
        "secret-readiness",
    )

    return rc, result


def apply_secret_result(document, rc, result):
    if (
        rc == 0
        and result is not None
        and result.get("result") == "pass"
    ):
        document["gates"]["secret_readiness"]["result"] = "pass"
        return True

    document["gates"]["secret_readiness"]["result"] = "blocked"
    document["decision"]["reasons"].append(
        "Secret readiness could not be proven."
    )
    return False


def registry_plan(
    document,
    container,
    authority_root,
    trivy_cache_dir,
):
    plan_rc, plan = run_json(
        [
            IMAGE_PLANNER,
            "--authority-root",
            authority_root,
            container,
        ],
        accepted_codes=(0, 1, 2),
    )

    if plan is None:
        document["gates"]["ownership"]["result"] = "blocked"
        document["decision"]["reasons"].append(
            "Candidate image planning could not be proven."
        )
        return

    validate_read_only_gate(
        plan,
        "candidate-planner",
    )

    authority = require_mapping(
        plan.get("authority"),
        "planner.authority",
    )
    runtime = require_mapping(
        plan.get("runtime"),
        "planner.runtime",
    )
    candidate = require_mapping(
        plan.get("candidate"),
        "planner.candidate",
    )
    comparison = require_mapping(
        plan.get("comparison"),
        "planner.comparison",
    )

    document["authority"] = {
        "revision": authority.get("revision"),
        "compose_files": list(
            authority.get("compose_files") or []
        ),
    }

    document["runtime"] = {
        "image": runtime.get("configured_image"),
        "image_id": runtime.get("image_id"),
        "digest": runtime.get("digest"),
        "platform": platform(
            runtime.get("os"),
            runtime.get("architecture"),
        ),
    }

    candidate_platform = require_mapping(
        candidate.get("platform"),
        "planner.candidate.platform",
    )

    document["candidate"] = {
        "image": candidate.get("image"),
        "index_digest": candidate.get("index_digest"),
        "platform_digest": candidate.get("platform_digest"),
        "platform": platform(
            candidate_platform.get("os"),
            candidate_platform.get("architecture"),
        ),
    }

    comparison_result = comparison.get("result")

    allowed_comparison_results = {
        "same",
        "upgrade",
        "downgrade-blocked",
        "ordering-unknown-blocked",
        "local-build-provenance-required",
    }

    if comparison_result not in allowed_comparison_results:
        die(
            "planner returned unsupported comparison result"
        )

    document["gates"]["comparison"]["result"] = comparison_result

    runtime_platform = document["runtime"]["platform"]
    candidate_platform_out = document["candidate"]["platform"]

    if (
        runtime_platform is not None
        and candidate_platform_out is not None
        and runtime_platform == candidate_platform_out
    ):
        document["gates"]["architecture"]["result"] = "pass"
    else:
        document["gates"]["architecture"]["result"] = "blocked"
        document["decision"]["reasons"].append(
            "Runtime and candidate platform identity do not match."
        )

    service = document["service"]["service"]

    secret_rc, secret_result = run_secret_readiness(
        authority_root,
        service,
    )
    secrets_ok = apply_secret_result(
        document,
        secret_rc,
        secret_result,
    )

    if comparison_result in {
        "downgrade-blocked",
        "ordering-unknown-blocked",
        "local-build-provenance-required",
    }:
        document["decision"]["result"] = "blocked"
        document["decision"]["proposed_action"] = "manual-review"
        document["decision"]["reasons"].append(
            "Image comparison policy did not permit automatic progression."
        )
        return

    if document["gates"]["architecture"]["result"] != "pass":
        document["decision"]["result"] = "blocked"
        document["decision"]["proposed_action"] = "manual-review"
        return

    if not secrets_ok:
        document["decision"]["result"] = "blocked"
        document["decision"]["proposed_action"] = "manual-review"
        return

    with tempfile.TemporaryDirectory(
        prefix="stage4-deployment-plan-"
    ) as tmpdir:
        plan_path = Path(tmpdir) / "candidate-plan.json"
        plan_path.write_text(
            json.dumps(plan, indent=2) + "\n"
        )

        security_rc, security = run_json(
            [
                SECURITY_GATE,
                "--plan",
                plan_path,
                "--cache-dir",
                trivy_cache_dir,
            ],
            accepted_codes=(0, 1, 2),
        )

    if security is None:
        document["gates"]["security"]["result"] = "blocked"
        document["decision"]["result"] = "blocked"
        document["decision"]["proposed_action"] = "manual-review"
        document["decision"]["reasons"].append(
            "Candidate security state could not be proven."
        )
        return

    validate_read_only_gate(
        security,
        "trivy-candidate-security",
    )

    security_result = security.get("result")

    if security_result == "pass" and security_rc == 0:
        document["gates"]["security"]["result"] = "pass"
    elif security_result == "security-blocked":
        document["gates"]["security"]["result"] = "security-blocked"
        document["decision"]["result"] = "blocked"
        document["decision"]["proposed_action"] = "manual-review"
        document["decision"]["reasons"].append(
            "Candidate contains blocking HIGH or CRITICAL vulnerabilities."
        )
        return
    else:
        document["gates"]["security"]["result"] = "blocked"
        document["decision"]["result"] = "blocked"
        document["decision"]["proposed_action"] = "manual-review"
        document["decision"]["reasons"].append(
            "Candidate security validation failed closed."
        )
        return

    if comparison_result == "same":
        document["decision"] = {
            "result": "no-change",
            "proposed_action": "none",
            "reasons": [
                "Runtime and candidate immutable image identity are unchanged.",
                "Architecture, security and secret-readiness gates passed.",
            ],
        }
        return

    if comparison_result == "upgrade":
        document["decision"] = {
            "result": "ready-for-review",
            "proposed_action": "deploy-registry-image",
            "reasons": [
                "Candidate is an allowed image upgrade.",
                "Architecture, security and secret-readiness gates passed.",
                "Deployment remains disabled pending human review.",
            ],
        }
        return

    die("unreachable registry decision state")


def local_build_plan(
    document,
    container,
    authority_root,
):
    provenance_rc, provenance = run_json(
        [
            PROVENANCE_GATE,
            "--container",
            container,
        ],
        accepted_codes=(0, 1, 2),
    )

    if provenance is None:
        document["gates"]["local_build_provenance"]["result"] = (
            "provenance-blocked"
        )
        document["decision"]["reasons"].append(
            "Local-build provenance could not be proven."
        )
        return

    validate_read_only_gate(
        provenance,
        "local-build-provenance",
    )

    builds = require_mapping(
        provenance.get("builds"),
        "provenance.builds",
    )

    build = require_mapping(
        builds.get(container),
        f"provenance.builds.{container}",
    )

    authority = require_mapping(
        build.get("authority"),
        "provenance.build.authority",
    )
    runtime = require_mapping(
        build.get("runtime"),
        "provenance.build.runtime",
    )
    compose = require_mapping(
        build.get("compose"),
        "provenance.build.compose",
    )

    document["authority"] = {
        "revision": authority.get("revision"),
        "compose_files": [
            require_string(
                compose.get("compose_file"),
                "provenance.compose.compose_file",
            )
        ],
    }

    document["runtime"] = {
        "image": runtime.get("expected_image"),
        "image_id": runtime.get("image_id"),
        "digest": None,
        "platform": None,
    }

    document["candidate"] = {
        "image": compose.get("image"),
        "index_digest": None,
        "platform_digest": None,
        "platform": None,
    }

    document["gates"]["comparison"]["result"] = (
        "local-build-provenance-required"
    )

    provenance_result = build.get("result")

    if provenance_result not in {
        "same",
        "rebuild-required",
        "provenance-blocked",
    }:
        die(
            "local-build provenance returned unsupported result"
        )

    document["gates"]["local_build_provenance"]["result"] = (
        provenance_result
    )

    secret_rc, secret_result = run_secret_readiness(
        authority_root,
        document["service"]["service"],
    )
    secrets_ok = apply_secret_result(
        document,
        secret_rc,
        secret_result,
    )

    if not secrets_ok:
        document["decision"]["result"] = "blocked"
        document["decision"]["proposed_action"] = "manual-review"
        return

    if provenance_result == "same" and provenance_rc == 0:
        document["decision"] = {
            "result": "no-change",
            "proposed_action": "none",
            "reasons": [
                "Local-build provenance is equivalent to authoritative source.",
                "Secret-readiness requirements passed.",
            ],
        }
        return

    if provenance_result == "rebuild-required":
        document["decision"] = {
            "result": "rebuild-required",
            "proposed_action": "rebuild-local-image",
            "reasons": [
                "Registered local-build inputs changed since the runtime image revision.",
                "Deployment remains disabled pending rebuild and review.",
            ],
        }
        return

    document["decision"] = {
        "result": "blocked",
        "proposed_action": "manual-review",
        "reasons": [
            "Local-build provenance could not be proven safely.",
        ],
    }


def validate_schema(document):
    schema = json.loads(
        SCHEMA_PATH.read_text()
    )

    validator = Draft202012Validator(schema)

    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )

    if not errors:
        return

    for error in errors:
        path = ".".join(
            str(part)
            for part in error.absolute_path
        )
        print(
            f"SCHEMA ERROR {path or '<root>'}: "
            f"{error.message}",
            file=sys.stderr,
        )

    die("generated deployment plan failed schema validation")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a non-secret, read-only Stage 4 deployment plan "
            "from the existing validation gates."
        )
    )

    parser.add_argument(
        "container",
        help="running container name to assess",
    )

    parser.add_argument(
        "--authority-root",
        required=True,
        help=(
            "clean authoritative docker-env checkout used by "
            "registry-image planning and secret readiness"
        ),
    )

    parser.add_argument(
        "--trivy-cache-dir",
        required=True,
        help="explicit persistent Trivy cache directory",
    )

    args = parser.parse_args()

    ownership_rc, ownership = run_json(
        [
            OWNERSHIP_RESOLVER,
            args.container,
        ],
        accepted_codes=(0,),
    )

    if ownership_rc != 0 or ownership is None:
        die("service ownership could not be resolved")

    document = base_document(ownership)

    authority = document["service"]["authority"]
    image_type = document["service"]["image_type"]

    if authority == "platform-exception":
        document["gates"]["ownership"]["result"] = "blocked"
        document["decision"] = {
            "result": "blocked",
            "proposed_action": "manual-review",
            "reasons": [
                "Service is an explicit platform exception.",
                "Stage 4 deployment planning is not authorised for this service.",
            ],
        }

    elif image_type == "registry-image":
        registry_plan(
            document,
            args.container,
            args.authority_root,
            args.trivy_cache_dir,
        )

    elif image_type == "local-build":
        local_build_plan(
            document,
            args.container,
            args.authority_root,
        )

    else:
        document["gates"]["ownership"]["result"] = "blocked"
        document["decision"] = {
            "result": "blocked",
            "proposed_action": "manual-review",
            "reasons": [
                "Service image type is unsupported.",
            ],
        }

    document["deployment"] = {
        "allowed": False,
        "performed": False,
    }

    validate_schema(document)

    print(
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
