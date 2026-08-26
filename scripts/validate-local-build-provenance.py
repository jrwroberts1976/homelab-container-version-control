#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml


EXIT_SAME = 0
EXIT_REBUILD_REQUIRED = 1
EXIT_BLOCKED = 2


def die(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(EXIT_BLOCKED)


def run(command, cwd=None):
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_yaml(path):
    try:
        return yaml.safe_load(path.read_text()) or {}
    except OSError as exc:
        die(f"cannot read {path}: {exc}")
    except yaml.YAMLError as exc:
        die(f"invalid YAML in {path}: {exc}")


def normalise_github_repository(remote):
    remote = remote.strip()

    patterns = (
        r"^https?://github\.com/(.+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/(.+?)(?:\.git)?/?$",
        r"^git@github\.com:(.+?)(?:\.git)?$",
    )

    for pattern in patterns:
        match = re.match(pattern, remote)

        if match:
            return match.group(1).removesuffix(".git")

    return None


def safe_repo_path(root, relative, description):
    path = (root / relative).resolve()

    try:
        path.relative_to(root.resolve())
    except ValueError:
        die(f"{description} escapes authority root: {relative}")

    return path


def git_authority(rule):
    root = Path(rule["authority_root"]).resolve()

    if not root.is_dir():
        die(f"authority root does not exist: {root}")

    proc = run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"]
    )

    if proc.returncode != 0 or proc.stdout.strip() != "true":
        die(f"authority root is not a Git worktree: {root}")

    proc = run(["git", "-C", str(root), "status", "--porcelain"])

    if proc.returncode != 0:
        die(f"unable to inspect Git status: {root}")

    clean = not proc.stdout.strip()

    proc = run(["git", "-C", str(root), "rev-parse", "HEAD"])

    if proc.returncode != 0:
        die(f"unable to resolve Git HEAD: {root}")

    revision = proc.stdout.strip()

    proc = run(["git", "-C", str(root), "remote", "get-url", "origin"])

    if proc.returncode != 0:
        die(f"unable to resolve Git origin: {root}")

    remote = proc.stdout.strip()
    repository = normalise_github_repository(remote)

    return {
        "root": root,
        "clean": clean,
        "revision": revision,
        "origin": remote,
        "repository": repository,
    }


def resolve_ownership(project_root, container):
    resolver = project_root / "scripts" / "resolve-service-ownership.sh"

    proc = run([str(resolver), container])

    if proc.returncode != 0:
        return None, "ownership resolver rejected container"

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, "ownership resolver returned invalid JSON"

    return data, None


def inspect_container(container):
    proc = run(["docker", "inspect", container])

    if proc.returncode != 0:
        return None, "container inspect failed"

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, "container inspect returned invalid JSON"

    if len(data) != 1:
        return None, "container inspect returned unexpected result count"

    return data[0], None


def inspect_image(image_id):
    proc = run(["docker", "image", "inspect", image_id])

    if proc.returncode != 0:
        return None, "runtime image inspect failed"

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, "runtime image inspect returned invalid JSON"

    if len(data) != 1:
        return None, "runtime image inspect returned unexpected result count"

    return data[0], None


def compose_service(rule, authority):
    root = authority["root"]
    compose_rel = rule["compose_file"]

    compose_path = safe_repo_path(
        root,
        compose_rel,
        "Compose file",
    )

    if not compose_path.is_file():
        return None, {
            "compose_present": False,
            "compose_valid": False,
            "service_present": False,
            "build_declared": False,
            "image_matches": False,
        }

    proc = run(
        [
            "docker",
            "compose",
            "-f",
            str(compose_path),
            "config",
            "--no-interpolate",
            "--format",
            "json",
        ],
        cwd=root,
    )

    if proc.returncode != 0:
        return None, {
            "compose_present": True,
            "compose_valid": False,
            "service_present": False,
            "build_declared": False,
            "image_matches": False,
        }

    try:
        model = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, {
            "compose_present": True,
            "compose_valid": False,
            "service_present": False,
            "build_declared": False,
            "image_matches": False,
        }

    service_name = rule["service"]
    service = (model.get("services") or {}).get(service_name)

    if not isinstance(service, dict):
        return None, {
            "compose_present": True,
            "compose_valid": True,
            "service_present": False,
            "build_declared": False,
            "image_matches": False,
        }

    build = service.get("build")

    arg_names = []

    if isinstance(build, dict):
        args = build.get("args") or {}

        if isinstance(args, dict):
            arg_names = sorted(args.keys())

    checks = {
        "compose_present": True,
        "compose_valid": True,
        "service_present": True,
        "build_declared": build is not None,
        "image_matches":
            service.get("image") == rule["expected_image"],
    }

    metadata = {
        "compose_file": compose_rel,
        "service": service_name,
        "image": service.get("image"),
        "build_declared": build is not None,
        "build_arg_names": arg_names,
    }

    return metadata, checks


def check_revision_exists(authority, revision):
    proc = run(
        [
            "git",
            "-C",
            str(authority["root"]),
            "cat-file",
            "-e",
            f"{revision}^{{commit}}",
        ]
    )

    return proc.returncode == 0


def check_ancestor(authority, revision):
    proc = run(
        [
            "git",
            "-C",
            str(authority["root"]),
            "merge-base",
            "--is-ancestor",
            revision,
            authority["revision"],
        ]
    )

    return proc.returncode == 0


def changed_build_inputs(authority, revision, inputs):
    root = authority["root"]

    validated_inputs = []

    for relative in inputs:
        safe_repo_path(root, relative, "build input")
        validated_inputs.append(relative)

    proc = run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--name-only",
            revision,
            authority["revision"],
            "--",
            *validated_inputs,
        ]
    )

    if proc.returncode != 0:
        return None

    return [
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip()
    ]


def validate_rule(project_root, name, rule, defaults):
    required = (
        "container",
        "service",
        "repository",
        "authority_root",
        "source_url",
        "strategy",
        "compose_file",
        "expected_image",
    )

    for field in required:
        if not isinstance(rule.get(field), str) or not rule[field]:
            die(f"{name}: required field missing: {field}")

    strategy = rule["strategy"]

    if strategy not in ("exact-head", "path-equivalence"):
        die(f"{name}: unsupported strategy: {strategy}")

    if strategy == "path-equivalence":
        inputs = rule.get("build_inputs")

        if not isinstance(inputs, list) or not inputs:
            die(f"{name}: path-equivalence requires build_inputs")

    authority = git_authority(rule)

    ownership, ownership_error = resolve_ownership(
        project_root,
        rule["container"],
    )

    container_data, container_error = inspect_container(
        rule["container"]
    )

    checks = {
        "authority_clean": authority["clean"],
        "authority_repository_matches":
            authority["repository"] == rule["repository"],
        "ownership_resolved": ownership_error is None,
        "ownership_local_build": False,
        "ownership_not_platform_exception": False,
        "ownership_repository_matches": False,
        "deployment_disabled": False,
        "container_present": container_error is None,
        "container_running": False,
        "runtime_config_image_matches": False,
        "runtime_image_identity_matches": False,
        "required_labels_present": False,
        "source_label_matches": False,
        "revision_label_valid": False,
        "revision_exists": False,
        "compose_present": False,
        "compose_valid": False,
        "compose_service_present": False,
        "compose_build_declared": False,
        "compose_image_matches": False,
    }

    if ownership is not None:
        checks["ownership_local_build"] = (
            ownership.get("image_type") == "local-build"
        )
        checks["ownership_not_platform_exception"] = (
            ownership.get("authority") != "platform-exception"
        )
        checks["ownership_repository_matches"] = (
            ownership.get("repository") == rule["repository"]
        )
        checks["deployment_disabled"] = (
            ownership.get("deployment_allowed") is False
        )

    compose_meta, compose_checks = compose_service(rule, authority)

    checks["compose_present"] = compose_checks["compose_present"]
    checks["compose_valid"] = compose_checks["compose_valid"]
    checks["compose_service_present"] = compose_checks["service_present"]
    checks["compose_build_declared"] = compose_checks["build_declared"]
    checks["compose_image_matches"] = compose_checks["image_matches"]

    image_data = None
    runtime_image_id = None
    labels = {}

    if container_data is not None:
        state = container_data.get("State") or {}
        config = container_data.get("Config") or {}

        checks["container_running"] = state.get("Running") is True
        checks["runtime_config_image_matches"] = (
            config.get("Image") == rule["expected_image"]
        )

        runtime_image_id = container_data.get("Image")

        if runtime_image_id:
            image_data, _ = inspect_image(runtime_image_id)

    if image_data is not None:
        checks["runtime_image_identity_matches"] = (
            image_data.get("Id") == runtime_image_id
        )
        labels = (image_data.get("Config") or {}).get("Labels") or {}

    required_labels = defaults.get("required_labels") or []

    checks["required_labels_present"] = (
        bool(required_labels)
        and all(
            isinstance(labels.get(label), str)
            and bool(labels[label].strip())
            for label in required_labels
        )
    )

    source_label = labels.get("org.opencontainers.image.source")
    revision_label = labels.get("org.opencontainers.image.revision")
    created_label = labels.get("org.opencontainers.image.created")

    checks["source_label_matches"] = (
        source_label == rule["source_url"]
    )

    checks["revision_label_valid"] = (
        isinstance(revision_label, str)
        and re.fullmatch(r"[0-9a-fA-F]{40}", revision_label) is not None
    )

    if checks["revision_label_valid"]:
        checks["revision_exists"] = check_revision_exists(
            authority,
            revision_label,
        )

    structural_checks = [
        checks["authority_clean"],
        checks["authority_repository_matches"],
        checks["ownership_resolved"],
        checks["ownership_local_build"],
        checks["ownership_not_platform_exception"],
        checks["ownership_repository_matches"],
        checks["deployment_disabled"],
        checks["container_present"],
        checks["container_running"],
        checks["runtime_config_image_matches"],
        checks["runtime_image_identity_matches"],
        checks["required_labels_present"],
        checks["source_label_matches"],
        checks["revision_label_valid"],
        checks["revision_exists"],
        checks["compose_present"],
        checks["compose_valid"],
        checks["compose_service_present"],
        checks["compose_build_declared"],
        checks["compose_image_matches"],
    ]

    strategy_checks = {}
    changed_paths = []

    if not all(structural_checks):
        result = "provenance-blocked"

    elif strategy == "exact-head":
        strategy_checks["revision_exact_head"] = (
            revision_label == authority["revision"]
        )

        result = (
            "same"
            if strategy_checks["revision_exact_head"]
            else "rebuild-required"
        )

    else:
        ancestor = check_ancestor(
            authority,
            revision_label,
        )

        strategy_checks["revision_is_ancestor"] = ancestor

        if not ancestor:
            result = "provenance-blocked"

        else:
            changed = changed_build_inputs(
                authority,
                revision_label,
                rule["build_inputs"],
            )

            if changed is None:
                strategy_checks["build_input_diff_resolved"] = False
                result = "provenance-blocked"
            else:
                strategy_checks["build_input_diff_resolved"] = True
                changed_paths = changed
                strategy_checks["build_inputs_unchanged"] = (
                    len(changed_paths) == 0
                )

                result = (
                    "same"
                    if not changed_paths
                    else "rebuild-required"
                )

    return {
        "container": rule["container"],
        "service": rule["service"],
        "repository": rule["repository"],
        "strategy": strategy,
        "authority": {
            "revision": authority["revision"],
            "clean": authority["clean"],
            "repository": authority["repository"],
        },
        "compose": compose_meta,
        "runtime": {
            "expected_image": rule["expected_image"],
            "image_id": runtime_image_id,
            "source": source_label,
            "revision": revision_label,
            "created": created_label,
        },
        "checks": checks,
        "strategy_checks": strategy_checks,
        "changed_build_inputs": changed_paths,
        "result": result,
        "deployment": {
            "allowed": False,
            "performed": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Stage 4 local-build provenance validator."
        )
    )

    parser.add_argument(
        "--registry",
        default=None,
        help="local-build provenance registry",
    )

    scope = parser.add_mutually_exclusive_group(required=True)

    scope.add_argument(
        "--container",
        help="validate one registered local-build container",
    )

    scope.add_argument(
        "--all",
        action="store_true",
        help="validate all registered local builds",
    )

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent

    registry_path = (
        Path(args.registry)
        if args.registry
        else project_root / "config" / "local-build-provenance.yml"
    )

    registry = load_yaml(registry_path)

    if registry.get("schema_version") != 1:
        die("unsupported local-build provenance schema")

    defaults = registry.get("defaults") or {}

    if defaults.get("validation") != "read-only":
        die("registry validation mode must be read-only")

    if defaults.get("deployment_allowed") is not False:
        die("registry must explicitly disable deployment")

    builds = registry.get("builds") or {}

    if not isinstance(builds, dict) or not builds:
        die("no local-build provenance rules registered")

    if args.all:
        selected = builds
        selected_container = None
    else:
        selected_container = args.container

        selected = {
            name: rule
            for name, rule in builds.items()
            if rule.get("container") == selected_container
        }

        if len(selected) != 1:
            die(
                f"expected one provenance rule for container "
                f"{selected_container}; found {len(selected)}"
            )

    results = {
        name: validate_rule(
            project_root,
            name,
            rule,
            defaults,
        )
        for name, rule in selected.items()
    }

    same = sum(
        item["result"] == "same"
        for item in results.values()
    )

    rebuild = sum(
        item["result"] == "rebuild-required"
        for item in results.values()
    )

    blocked = sum(
        item["result"] == "provenance-blocked"
        for item in results.values()
    )

    if blocked:
        overall = "provenance-blocked"
        exit_code = EXIT_BLOCKED
    elif rebuild:
        overall = "rebuild-required"
        exit_code = EXIT_REBUILD_REQUIRED
    else:
        overall = "same"
        exit_code = EXIT_SAME

    output = {
        "schema_version": 1,
        "mode": "read-only",
        "gate": "local-build-provenance",
        "scope": {
            "container": selected_container,
            "all": args.all,
        },
        "summary": {
            "builds_checked": len(results),
            "same": same,
            "rebuild_required": rebuild,
            "blocked": blocked,
        },
        "builds": results,
        "result": overall,
        "deployment": {
            "allowed": False,
            "performed": False,
        },
    }

    json.dump(output, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
