#!/usr/bin/env python3
"""Phase 1 estate updater front end.

This increment validates high-level caller intent and resolves reviewed routing
metadata only. It deliberately performs no host contact and no mutation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]*$")
MANIFEST_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.json$")

FINAL_ACTIONS = {"inspect", "prepare", "deploy", "rollback"}
PHASE1_ACTIONS = {"inspect"}
BACKENDS = {"docker-compose-stage6", "kubernetes-stage6"}
COVERAGE_STATES = {
    "managed-tested",
    "pending-onboarding",
    "pending-framework",
    "pinned-manual",
    "platform-managed",
}
CALLER_OPTIONS = ("--service", "--version", "--hosts", "--action")


class RouterError(Exception):
    pass


def fail(message: str) -> "NoReturn":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def reject_duplicate_options(argv: list[str]) -> None:
    for option in CALLER_OPTIONS:
        count = sum(
            1
            for token in argv
            if token == option or token.startswith(option + "=")
        )
        if count > 1:
            fail(f"duplicate caller option rejected: {option}")


def load_catalog() -> tuple[dict[str, Any], Path]:
    repo_root = Path(__file__).resolve().parent.parent
    path = repo_root / "config" / "estate-updater-catalog.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RouterError(f"cannot read reviewed catalogue: {exc}") from exc

    try:
        catalog = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RouterError(f"reviewed catalogue is invalid JSON: {exc}") from exc

    validate_catalog(catalog)
    return catalog, path


def validate_catalog(catalog: Any) -> None:
    if not isinstance(catalog, dict):
        raise RouterError("catalogue root must be an object")
    if catalog.get("schema_version") != 1:
        raise RouterError("catalogue schema_version must be 1")
    if catalog.get("artifact") != "estate-updater-catalog":
        raise RouterError("catalogue artifact identity is invalid")

    hosts = catalog.get("hosts")
    services = catalog.get("services")
    if not isinstance(hosts, dict) or not hosts:
        raise RouterError("catalogue hosts must be a non-empty object")
    if not isinstance(services, dict) or not services:
        raise RouterError("catalogue services must be a non-empty object")

    for host_name, host in hosts.items():
        if not isinstance(host_name, str) or not HOST_RE.fullmatch(host_name):
            raise RouterError(f"invalid catalogue host name: {host_name!r}")
        if not isinstance(host, dict):
            raise RouterError(f"host metadata must be an object: {host_name}")
        if host.get("backend") not in BACKENDS:
            raise RouterError(f"unsupported reviewed backend for {host_name}")
        if not isinstance(host.get("platform"), str) or "/" not in host["platform"]:
            raise RouterError(f"invalid reviewed platform for {host_name}")
        if not isinstance(host.get("backend_available"), bool):
            raise RouterError(f"backend_available must be boolean for {host_name}")

    for service_name, service in services.items():
        if not isinstance(service_name, str) or not SERVICE_RE.fullmatch(service_name):
            raise RouterError(f"invalid catalogue service name: {service_name!r}")
        if not isinstance(service, dict):
            raise RouterError(f"service metadata must be an object: {service_name}")

        desired = service.get("desired_version")
        if desired is not None and (
            not isinstance(desired, str)
            or not desired
            or len(desired) > 128
            or not VERSION_RE.fullmatch(desired)
        ):
            raise RouterError(f"invalid desired version for {service_name}")

        service_hosts = service.get("hosts")
        if not isinstance(service_hosts, dict) or not service_hosts:
            raise RouterError(f"service hosts must be non-empty for {service_name}")

        for host_name, entry in service_hosts.items():
            if host_name not in hosts:
                raise RouterError(
                    f"service {service_name} references unknown host {host_name}"
                )
            if not isinstance(entry, dict):
                raise RouterError(
                    f"service-host metadata must be an object: {service_name}/{host_name}"
                )
            if entry.get("coverage") not in COVERAGE_STATES:
                raise RouterError(
                    f"invalid coverage state for {service_name}/{host_name}"
                )
            if not isinstance(entry.get("class"), str) or not entry["class"]:
                raise RouterError(f"missing class for {service_name}/{host_name}")
            if not isinstance(entry.get("configured_image"), str) or not entry["configured_image"]:
                raise RouterError(
                    f"missing reviewed configured image for {service_name}/{host_name}"
                )
            if not isinstance(entry.get("inspect_ready"), bool):
                raise RouterError(
                    f"inspect_ready must be boolean for {service_name}/{host_name}"
                )
            if entry["inspect_ready"] and not hosts[host_name]["backend_available"]:
                raise RouterError(
                    f"inspect_ready cannot be true while backend unavailable: {service_name}/{host_name}"
                )
            manifest = entry.get("manifest")
            if manifest is not None and (
                not isinstance(manifest, str) or not MANIFEST_RE.fullmatch(manifest)
            ):
                raise RouterError(
                    f"unsafe reviewed manifest filename for {service_name}/{host_name}"
                )


def parse_hosts(value: str | None, approved: list[str], all_hosts: dict[str, Any]) -> list[str]:
    if value is None:
        return approved
    if not value:
        fail("--hosts must not be empty")

    requested = value.split(",")
    if any(not item for item in requested):
        fail("--hosts contains an empty host")
    if len(set(requested)) != len(requested):
        fail("duplicate host rejected in --hosts")

    for host in requested:
        if not HOST_RE.fullmatch(host):
            fail(f"invalid host name: {host}")
        if host not in all_hosts:
            fail(f"unknown host: {host}")
        if host not in approved:
            fail(f"service is not approved on host: {host}")

    return requested


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homelab-update",
        description=(
            "Resolve reviewed estate-update intent. Phase 1 is routing-only and "
            "performs no host contact."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--service", required=True)
    parser.add_argument("--version")
    parser.add_argument("--hosts")
    parser.add_argument("--action", required=True)
    return parser


def main(argv: list[str]) -> int:
    reject_duplicate_options(argv)
    args = build_parser().parse_args(argv)

    if not SERVICE_RE.fullmatch(args.service):
        fail("invalid service name")
    if args.action not in FINAL_ACTIONS:
        fail(f"unsupported action: {args.action}")
    if args.action not in PHASE1_ACTIONS:
        fail(f"action is fail-closed in Phase 1: {args.action}")

    if args.version is not None:
        if not args.version or len(args.version) > 128 or not VERSION_RE.fullmatch(args.version):
            fail("invalid version")

    try:
        catalog, catalog_path = load_catalog()
    except RouterError as exc:
        fail(str(exc))

    services = catalog["services"]
    hosts = catalog["hosts"]
    service = services.get(args.service)
    if service is None:
        fail(f"unknown service: {args.service}")

    desired = service["desired_version"]
    if args.version is not None:
        if desired is None:
            fail("caller version rejected because no reviewed desired version exists")
        if args.version != desired:
            fail(
                f"caller version does not match reviewed desired version: {args.version} != {desired}"
            )

    approved_hosts = list(service["hosts"].keys())
    selected_hosts = parse_hosts(args.hosts, approved_hosts, hosts)

    targets: list[dict[str, Any]] = []
    for host_name in selected_hosts:
        host = hosts[host_name]
        entry = service["hosts"][host_name]
        target: dict[str, Any] = {
            "host": host_name,
            "backend": host["backend"],
            "platform": host["platform"],
            "backend_available": host["backend_available"],
            "coverage": entry["coverage"],
            "class": entry["class"],
            "inspect_ready": entry["inspect_ready"],
            "current_version": entry.get("current_version"),
            "configured_image": entry["configured_image"],
        }
        for optional in (
            "manifest",
            "blocker",
            "namespace",
            "controller_kind",
            "controller_name",
        ):
            if optional in entry:
                target[optional] = entry[optional]
        targets.append(target)

    result = {
        "schema_version": 1,
        "artifact": "estate-update-routing-plan",
        "phase": "router-only",
        "catalog": str(catalog_path.relative_to(catalog_path.parent.parent)),
        "action": args.action,
        "service": args.service,
        "requested_version": args.version,
        "desired_version": desired,
        "targets": targets,
        "all_targets_inspect_ready": all(t["inspect_ready"] for t in targets),
        "host_contact_performed": False,
        "mutation_allowed": False,
        "result": "resolved-read-only-routing-plan",
    }

    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
