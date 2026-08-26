#!/usr/bin/env python3

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import yaml


def validation_error(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def run(command):
    proc = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc


def load_yaml(path):
    try:
        return yaml.safe_load(path.read_text()) or {}
    except OSError as exc:
        validation_error(f"cannot read {path}: {exc}")
    except yaml.YAMLError as exc:
        validation_error(f"invalid YAML in {path}: {exc}")


def normalise_github_remote(remote):
    remote = remote.strip()

    patterns = (
        r"^https?://github\.com/(.+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(.+?)(?:\.git)?$",
        r"^git@github\.com:(.+?)(?:\.git)?$",
    )

    for pattern in patterns:
        match = re.match(pattern, remote)
        if match:
            return match.group(1).removesuffix(".git")

    return None


def validate_authority(root, expected_repository):
    if not root.is_dir():
        validation_error(f"authority root does not exist: {root}")

    proc = run(["git", "-C", str(root), "status", "--porcelain"])
    if proc.returncode != 0:
        validation_error("unable to inspect authority Git worktree")

    if proc.stdout.strip():
        validation_error("authority Git worktree is not clean")

    proc = run(["git", "-C", str(root), "remote", "get-url", "origin"])
    if proc.returncode != 0:
        validation_error("authority Git origin is unavailable")

    actual_repository = normalise_github_remote(proc.stdout)
    if actual_repository != expected_repository:
        validation_error(
            "authority repository mismatch: "
            f"expected {expected_repository}, got {actual_repository}"
        )

    proc = run(["git", "-C", str(root), "rev-parse", "HEAD"])
    if proc.returncode != 0:
        validation_error("unable to determine authority Git revision")

    return {
        "repository": actual_repository,
        "revision": proc.stdout.strip(),
        "clean": True,
    }


def find_compose_service(root, service_name):
    matches = []

    for pattern in ("stacks/**/*.yml", "stacks/**/*.yaml"):
        for path in sorted(root.glob(pattern)):
            try:
                data = yaml.safe_load(path.read_text()) or {}
            except (OSError, yaml.YAMLError):
                continue

            services = data.get("services") or {}

            if service_name in services:
                matches.append((path, data, services[service_name] or {}))

    if len(matches) != 1:
        return None, (
            f"expected exactly one Compose definition for service "
            f"{service_name}; found {len(matches)}"
        )

    return matches[0], None


def service_secret_names(service):
    result = set()

    for item in service.get("secrets") or []:
        if isinstance(item, str):
            result.add(item)
        elif isinstance(item, dict):
            source = item.get("source")
            if source:
                result.add(source)

    return result


def compose_secret_validation(
    root,
    service_name,
    compose_secret,
    runtime_path,
):
    match, error = find_compose_service(root, service_name)

    if error:
        return {
            "service_found": False,
            "service_secret_declared": False,
            "top_level_secret_declared": False,
            "runtime_path_matches_compose": False,
            "error": error,
        }

    path, data, service = match
    service_secrets = service_secret_names(service)

    top_secrets = data.get("secrets") or {}
    definition = top_secrets.get(compose_secret)

    top_declared = isinstance(definition, dict)
    compose_path = (
        definition.get("file")
        if top_declared
        else None
    )

    return {
        "compose_file": str(path.relative_to(root)),
        "service_found": True,
        "service_secret_declared": compose_secret in service_secrets,
        "top_level_secret_declared": top_declared,
        "runtime_path_matches_compose": compose_path == runtime_path,
    }


def expected_key_is_encrypted(path, key):
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return False

    prefix = f"{key}="

    for line in lines:
        if line.startswith(prefix):
            value = line[len(prefix):]
            return value.startswith("ENC[AES256_GCM,")

    return False


def sops_structure_valid(path):
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return False

    return (
        "sops_mac=ENC[" in text
        and "sops_version=" in text
        and "sops_age__list_" in text
    )


def parse_dotenv(text):
    values = {}

    for raw in text.splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value

    return values


def validate_secret(root, name, rule):
    encrypted_rel = rule.get("encrypted_source")
    recovery_key = rule.get("recovery_key")
    runtime_path_text = rule.get("runtime_path")
    required_mode = str(rule.get("required_mode", ""))
    service_name = rule.get("service")
    compose_secret = rule.get("compose_secret")

    if not all(
        isinstance(value, str) and value
        for value in (
            encrypted_rel,
            recovery_key,
            runtime_path_text,
            required_mode,
            service_name,
            compose_secret,
        )
    ):
        validation_error(f"secret rule {name} is incomplete")

    encrypted_path = (root / encrypted_rel).resolve()

    try:
        encrypted_path.relative_to(root.resolve())
    except ValueError:
        validation_error(
            f"secret rule {name} encrypted source escapes authority root"
        )

    runtime_path = Path(runtime_path_text)

    result = {
        "service": service_name,
        "compose_secret": compose_secret,
        "encrypted_source": encrypted_rel,
        "recovery_key": recovery_key,
        "runtime_path": runtime_path_text,
        "required_mode": required_mode,
        "checks": {},
    }

    checks = result["checks"]

    compose = compose_secret_validation(
        root,
        service_name,
        compose_secret,
        runtime_path_text,
    )
    checks["compose"] = compose

    checks["encrypted_source_present"] = encrypted_path.is_file()
    checks["sops_structure"] = (
        encrypted_path.is_file()
        and sops_structure_valid(encrypted_path)
    )
    checks["expected_key_encrypted"] = (
        encrypted_path.is_file()
        and expected_key_is_encrypted(encrypted_path, recovery_key)
    )

    recovered = None
    decryptable = False
    recovery_key_present = False
    recovery_nonempty = False

    if encrypted_path.is_file():
        proc = run(
            [
                "sops",
                "--decrypt",
                "--input-type",
                rule.get("encrypted_format", "dotenv"),
                "--output-type",
                "dotenv",
                str(encrypted_path),
            ]
        )

        decryptable = proc.returncode == 0

        if decryptable:
            values = parse_dotenv(proc.stdout)

            if recovery_key in values:
                recovery_key_present = True
                recovered = values[recovery_key]
                recovery_nonempty = recovered != ""

    checks["decryptable"] = decryptable
    checks["recovery_key_present"] = recovery_key_present
    checks["recovery_nonempty"] = recovery_nonempty

    runtime_present = runtime_path.is_file()
    runtime_nonempty = False
    exact_match = False
    mode = None
    permissions_ok = False

    if runtime_present:
        try:
            info = runtime_path.stat()
            mode = f"{stat.S_IMODE(info.st_mode):04o}"
            permissions_ok = mode == required_mode

            deployed = runtime_path.read_text().rstrip("\r\n")
            runtime_nonempty = deployed != ""

            if recovered is not None:
                exact_match = recovered == deployed
        except OSError:
            pass

    checks["runtime_present"] = runtime_present
    checks["runtime_nonempty"] = runtime_nonempty
    checks["exact_recovery_match"] = exact_match
    checks["runtime_mode"] = mode
    checks["permissions_ok"] = permissions_ok

    required_checks = [
        compose.get("service_found") is True,
        compose.get("service_secret_declared") is True,
        compose.get("top_level_secret_declared") is True,
        compose.get("runtime_path_matches_compose") is True,
        checks["encrypted_source_present"],
        checks["sops_structure"],
        checks["expected_key_encrypted"],
        checks["decryptable"],
        checks["recovery_key_present"],
        checks["recovery_nonempty"],
        checks["runtime_present"],
        checks["runtime_nonempty"],
        checks["permissions_ok"],
    ]

    if rule.get("require_exact_recovery_match", True):
        required_checks.append(checks["exact_recovery_match"])

    result["result"] = (
        "pass"
        if all(required_checks)
        else "readiness-blocked"
    )

    return result


def environment_value(service, key):
    environment = service.get("environment") or {}

    if isinstance(environment, dict):
        value = environment.get(key)
        return value

    if isinstance(environment, list):
        prefix = f"{key}="

        for item in environment:
            if isinstance(item, str) and item.startswith(prefix):
                return item[len(prefix):]

    return None


def runtime_environment(container, key):
    proc = run(["docker", "inspect", container])

    if proc.returncode != 0:
        return {
            "container_present": False,
            "runtime_key_present": False,
            "runtime_nonempty": False,
            "value": None,
        }

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "container_present": False,
            "runtime_key_present": False,
            "runtime_nonempty": False,
            "value": None,
        }

    entries = (data[0].get("Config") or {}).get("Env") or []
    prefix = f"{key}="
    matches = [
        item[len(prefix):]
        for item in entries
        if isinstance(item, str) and item.startswith(prefix)
    ]

    return {
        "container_present": True,
        "runtime_key_present": len(matches) == 1,
        "runtime_nonempty": len(matches) == 1 and matches[0] != "",
        "value": matches[0] if len(matches) == 1 else None,
    }


def validate_runtime_configuration(root, name, rule):
    service_name = rule.get("service")
    source_path_text = rule.get("source_path")
    source_key = rule.get("source_key")
    runtime_key = rule.get("runtime_environment_key")

    if not all(
        isinstance(value, str) and value
        for value in (
            service_name,
            source_path_text,
            source_key,
            runtime_key,
        )
    ):
        validation_error(
            f"runtime configuration rule {name} is incomplete"
        )

    match, error = find_compose_service(root, service_name)

    checks = {
        "compose_service_found": error is None,
        "compose_variable_reference": False,
        "source_present": False,
        "source_key_present": False,
        "source_nonempty": False,
        "runtime_container_present": False,
        "runtime_key_present": False,
        "runtime_nonempty": False,
        "exact_runtime_match": False,
    }

    expected_reference = f"${{{source_key}}}"

    if error is None:
        _, _, service = match
        checks["compose_variable_reference"] = (
            environment_value(service, runtime_key)
            == expected_reference
        )

    source_path = Path(source_path_text)
    source_value = None

    if source_path.is_file():
        checks["source_present"] = True

        try:
            values = parse_dotenv(source_path.read_text())
        except OSError:
            values = {}

        if source_key in values:
            checks["source_key_present"] = True
            source_value = values[source_key]
            checks["source_nonempty"] = source_value != ""

    runtime = runtime_environment(service_name, runtime_key)

    checks["runtime_container_present"] = runtime["container_present"]
    checks["runtime_key_present"] = runtime["runtime_key_present"]
    checks["runtime_nonempty"] = runtime["runtime_nonempty"]

    if source_value is not None and runtime["value"] is not None:
        checks["exact_runtime_match"] = (
            source_value == runtime["value"]
        )

    required_checks = [
        checks["compose_service_found"],
        checks["compose_variable_reference"],
        checks["source_present"],
        checks["source_key_present"],
        checks["source_nonempty"],
        checks["runtime_container_present"],
        checks["runtime_key_present"],
        checks["runtime_nonempty"],
    ]

    if rule.get("require_exact_runtime_match", True):
        required_checks.append(checks["exact_runtime_match"])

    return {
        "service": service_name,
        "source_type": rule.get("source_type"),
        "source_path": source_path_text,
        "source_key": source_key,
        "runtime_environment_key": runtime_key,
        "checks": checks,
        "result": (
            "pass"
            if all(required_checks)
            else "readiness-blocked"
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Stage 4 secret and runtime-configuration "
            "readiness validator."
        )
    )

    parser.add_argument(
        "--authority-root",
        required=True,
        help="clean authoritative Git checkout",
    )

    parser.add_argument(
        "--registry",
        default=None,
        help="secret-readiness registry path",
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--service",
        help="validate readiness rules for one service",
    )

    group.add_argument(
        "--all",
        action="store_true",
        help="validate all registered readiness rules",
    )

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    registry_path = (
        Path(args.registry)
        if args.registry
        else project_root / "config" / "secret-readiness.yml"
    )

    registry = load_yaml(registry_path)

    if registry.get("schema_version") != 1:
        validation_error("unsupported secret-readiness schema")

    authority_rule = registry.get("authority") or {}
    expected_repository = authority_rule.get("repository")

    if not expected_repository:
        validation_error("authority repository missing from registry")

    authority_root = Path(args.authority_root).resolve()
    authority = validate_authority(
        authority_root,
        expected_repository,
    )

    sops_policy = authority_rule.get("sops_policy")
    if not sops_policy:
        validation_error("SOPS policy path missing from registry")

    sops_policy_path = authority_root / sops_policy
    if not sops_policy_path.is_file():
        validation_error("SOPS policy file is missing")

    if run(["sops", "--version"]).returncode != 0:
        validation_error("sops is unavailable")

    secret_rules = registry.get("secrets") or {}
    config_rules = registry.get("runtime_configuration") or {}

    if args.all:
        selected_secrets = secret_rules
        selected_config = config_rules
        selected_service = None
    else:
        selected_service = args.service

        selected_secrets = {
            name: rule
            for name, rule in secret_rules.items()
            if rule.get("service") == selected_service
        }

        selected_config = {
            name: rule
            for name, rule in config_rules.items()
            if rule.get("service") == selected_service
        }

    secret_results = {
        name: validate_secret(authority_root, name, rule)
        for name, rule in selected_secrets.items()
    }

    config_results = {
        name: validate_runtime_configuration(
            authority_root,
            name,
            rule,
        )
        for name, rule in selected_config.items()
    }

    blocked = (
        sum(
            item["result"] != "pass"
            for item in secret_results.values()
        )
        +
        sum(
            item["result"] != "pass"
            for item in config_results.values()
        )
    )

    checked = len(secret_results) + len(config_results)

    overall = "pass" if blocked == 0 else "readiness-blocked"

    output = {
        "schema_version": 1,
        "mode": "read-only",
        "gate": "secret-readiness",
        "scope": {
            "service": selected_service,
            "all": args.all,
        },
        "authority": authority,
        "sops_policy": sops_policy,
        "secrets": secret_results,
        "runtime_configuration": config_results,
        "summary": {
            "rules_checked": checked,
            "rules_blocked": blocked,
        },
        "result": overall,
        "deployment": {
            "allowed": False,
            "performed": False,
        },
    }

    json.dump(output, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    raise SystemExit(0 if overall == "pass" else 1)


if __name__ == "__main__":
    main()
