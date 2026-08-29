#!/usr/bin/env python3
"""Estate updater front end.

Phase 2B keeps routing fail-closed for unsupported targets and adds one reviewed
live read-only adapter: Homepage steady-state inspection on local TestServer.
No prepare, deploy or rollback execution path exists in this front end.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]*$")
MANIFEST_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.json$")

FINAL_ACTIONS = {"inspect", "prepare", "deploy", "rollback"}
AVAILABLE_ACTIONS = {"inspect"}
BACKENDS = {"docker-compose-stage6", "kubernetes-stage6"}
COVERAGE_STATES = {
    "managed-tested",
    "pending-onboarding",
    "pending-framework",
    "pinned-manual",
    "platform-managed",
}
CALLER_OPTIONS = ("--service", "--version", "--hosts", "--action")

INSTALLED_SELF = Path("/usr/local/bin/homelab-update")
INSTALLED_CATALOG = Path("/etc/homelab-stage6/estate-updater-catalog.json")
STEADY_INSPECTOR = Path("/usr/local/libexec/homelab-stage6-steady-inspect")
TESTSERVER = "TestServer"
FIXED_ENV = {
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/root",
    "LANG": "C",
    "LC_ALL": "C",
}


class RouterError(Exception):
    pass


def fail(message: str) -> NoReturn:
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


def source_catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "estate-updater-catalog.json"


def is_installed_mode() -> bool:
    try:
        return Path(__file__).resolve() == INSTALLED_SELF.resolve(strict=False)
    except OSError:
        return False


def load_catalog() -> tuple[dict[str, Any], Path]:
    path = INSTALLED_CATALOG if is_installed_mode() else source_catalog_path()
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
                    f"unsafe reviewed transition manifest filename for {service_name}/{host_name}"
                )

            steady_manifest = entry.get("steady_state_manifest")
            if steady_manifest is not None and (
                not isinstance(steady_manifest, str)
                or not MANIFEST_RE.fullmatch(steady_manifest)
            ):
                raise RouterError(
                    f"unsafe reviewed steady-state manifest filename for {service_name}/{host_name}"
                )

            if entry["inspect_ready"]:
                if entry.get("blocker") is not None:
                    raise RouterError(
                        f"inspect-ready target must not retain blocker: {service_name}/{host_name}"
                    )
                if (
                    host_name != TESTSERVER
                    or hosts[host_name]["backend"] != "docker-compose-stage6"
                    or steady_manifest is None
                ):
                    raise RouterError(
                        f"Phase 2B inspect-ready target lacks supported local steady-state contract: {service_name}/{host_name}"
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
            "Resolve reviewed estate-update intent and, only for explicitly "
            "inspect-ready targets, perform the reviewed read-only inspection."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--service", required=True)
    parser.add_argument("--version")
    parser.add_argument("--hosts")
    parser.add_argument("--action", required=True)
    return parser


def require_secure_regular_file(path: Path, executable: bool = False) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise RouterError(f"required installed file unavailable: {path}: {exc}") from exc

    if stat.S_ISLNK(info.st_mode):
        raise RouterError(f"installed file must not be a symlink: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise RouterError(f"installed path is not a regular file: {path}")
    if info.st_uid != 0 or info.st_gid != 0:
        raise RouterError(f"installed file is not root:root: {path}")
    if info.st_mode & 0o022:
        raise RouterError(f"installed file is group/other writable: {path}")
    if executable and not (info.st_mode & stat.S_IXUSR):
        raise RouterError(f"installed executable is not owner-executable: {path}")


def current_short_hostname() -> str:
    return os.uname().nodename.split(".", 1)[0]


def validate_inspection_evidence(
    evidence: Any,
    service: str,
    target: dict[str, Any],
    desired_version: str | None,
) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise RouterError("steady-state inspector output must be a JSON object")
    if evidence.get("schema_version") != 1:
        raise RouterError("steady-state inspector schema mismatch")
    if evidence.get("artifact") != "service-steady-state-inspection":
        raise RouterError("steady-state inspector artifact mismatch")
    if evidence.get("mode") != "read-only":
        raise RouterError("steady-state inspector mode is not read-only")
    if evidence.get("service") != service or evidence.get("host") != target["host"]:
        raise RouterError("steady-state inspector target mismatch")
    if evidence.get("mutation_allowed") is not False:
        raise RouterError("steady-state inspector did not prove mutation disabled")

    deployment = evidence.get("deployment")
    if not isinstance(deployment, dict):
        raise RouterError("steady-state inspector deployment evidence missing")
    if deployment.get("allowed") is not False or deployment.get("performed") is not False:
        raise RouterError("steady-state inspector did not prove deployment disabled")
    if evidence.get("result") != "steady-state-verified":
        raise RouterError("steady-state inspector did not verify desired state")

    desired = evidence.get("desired")
    if not isinstance(desired, dict):
        raise RouterError("steady-state inspector desired-state evidence missing")
    if desired.get("configured_image") != target["configured_image"]:
        raise RouterError("steady-state inspector configured image differs from reviewed route")
    if desired.get("version") != desired_version:
        raise RouterError("steady-state inspector version differs from reviewed desired version")

    manifest = evidence.get("manifest")
    if not isinstance(manifest, dict):
        raise RouterError("steady-state inspector manifest evidence missing")
    expected_manifest = f"/etc/homelab-stage6/steady-state/{target['steady_state_manifest']}"
    if manifest.get("path") != expected_manifest:
        raise RouterError("steady-state inspector manifest path differs from reviewed route")

    return evidence


def execute_local_testserver_inspection(
    service: str,
    target: dict[str, Any],
    desired_version: str | None,
) -> dict[str, Any]:
    if not is_installed_mode():
        raise RouterError(
            "live inspection requires the installed root-owned homelab-update front end"
        )
    if os.geteuid() != 0:
        raise RouterError("live inspection requires root privilege")
    if current_short_hostname() != TESTSERVER:
        raise RouterError("local TestServer inspection requested from the wrong host")
    if target.get("host") != TESTSERVER or target.get("backend") != "docker-compose-stage6":
        raise RouterError("unsupported Phase 2B live inspection target")

    require_secure_regular_file(INSTALLED_SELF, executable=True)
    require_secure_regular_file(INSTALLED_CATALOG)
    require_secure_regular_file(STEADY_INSPECTOR, executable=True)

    try:
        completed = subprocess.run(
            [str(STEADY_INSPECTOR), service],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            shell=False,
            timeout=120,
            env=FIXED_ENV,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RouterError(f"steady-state inspector execution failed: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        if len(detail) > 2000:
            detail = detail[:2000] + "..."
        raise RouterError(
            f"steady-state inspector rejected live state (rc={completed.returncode}): {detail}"
        )

    try:
        evidence = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RouterError("steady-state inspector returned invalid JSON") from exc

    return validate_inspection_evidence(evidence, service, target, desired_version)


def build_targets(
    service: dict[str, Any],
    selected_hosts: list[str],
    hosts: dict[str, Any],
) -> list[dict[str, Any]]:
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
            "steady_state_manifest",
            "blocker",
            "namespace",
            "controller_kind",
            "controller_name",
        ):
            if optional in entry:
                target[optional] = entry[optional]
        targets.append(target)
    return targets


def routing_result(
    catalog_path: Path,
    args: argparse.Namespace,
    desired: str | None,
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        catalog_display = str(catalog_path.relative_to(catalog_path.parent.parent))
    except ValueError:
        catalog_display = str(catalog_path)

    return {
        "schema_version": 1,
        "artifact": "estate-update-routing-plan",
        "phase": "router-only",
        "catalog": catalog_display,
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


def main(argv: list[str]) -> int:
    reject_duplicate_options(argv)
    args = build_parser().parse_args(argv)

    if not SERVICE_RE.fullmatch(args.service):
        fail("invalid service name")
    if args.action not in FINAL_ACTIONS:
        fail(f"unsupported action: {args.action}")
    if args.action not in AVAILABLE_ACTIONS:
        fail(f"action is fail-closed: {args.action}")

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
    targets = build_targets(service, selected_hosts, hosts)

    if not all(target["inspect_ready"] for target in targets):
        result = routing_result(catalog_path, args, desired, targets)
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    if len(targets) != 1:
        fail("Phase 2B live inspection supports exactly one reviewed target")

    try:
        evidence = execute_local_testserver_inspection(
            args.service,
            targets[0],
            desired,
        )
    except RouterError as exc:
        fail(str(exc))

    targets[0]["inspection"] = evidence
    result = {
        "schema_version": 1,
        "artifact": "estate-update-inspection",
        "phase": "live-read-only-inspection",
        "catalog": str(INSTALLED_CATALOG),
        "action": args.action,
        "service": args.service,
        "requested_version": args.version,
        "desired_version": desired,
        "targets": targets,
        "all_targets_inspect_ready": True,
        "host_contact_performed": True,
        "mutation_allowed": False,
        "deployment": {"allowed": False, "performed": False},
        "result": "steady-state-verified",
    }

    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
