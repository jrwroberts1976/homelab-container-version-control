#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
ROUTER = ROOT / "scripts" / "homelab-update.py"
CATALOG = ROOT / "config" / "estate-updater-catalog.json"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROUTER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def expect_routing_pass(name: str, *args: str) -> dict:
    result = run(*args)
    if result.returncode != 0:
        raise AssertionError(
            f"{name}: expected success, rc={result.returncode}, stderr={result.stderr!r}"
        )
    data = json.loads(result.stdout)
    if data.get("host_contact_performed") is not False:
        raise AssertionError(f"{name}: host contact was not proven false")
    if data.get("mutation_allowed") is not False:
        raise AssertionError(f"{name}: mutation was not proven false")
    if data.get("phase") != "router-only":
        raise AssertionError(f"{name}: unexpected phase")
    print(f"PASS: {name}")
    return data


def expect_fail(name: str, *args: str) -> None:
    result = run(*args)
    if result.returncode == 0:
        raise AssertionError(f"{name}: expected fail-closed rejection")
    print(f"PASS: {name} -> REJECTED")


def load_router_module():
    spec = importlib.util.spec_from_file_location("homelab_update_under_test", ROUTER)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load homelab-update module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def homepage_target() -> tuple[dict, dict, str]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    service = catalog["services"]["homepage"]
    entry = service["hosts"]["TestServer"]
    host = catalog["hosts"]["TestServer"]
    target = {
        "host": "TestServer",
        "backend": host["backend"],
        "platform": host["platform"],
        "backend_available": host["backend_available"],
        "coverage": entry["coverage"],
        "class": entry["class"],
        "inspect_ready": entry["inspect_ready"],
        "current_version": entry.get("current_version"),
        "configured_image": entry["configured_image"],
        "manifest": entry["manifest"],
        "steady_state_manifest": entry["steady_state_manifest"],
    }
    return service, target, service["desired_version"]


def reviewed_homepage_evidence(target: dict, desired_version: str) -> dict:
    return {
        "schema_version": 1,
        "artifact": "service-steady-state-inspection",
        "mode": "read-only",
        "service": "homepage",
        "host": "TestServer",
        "manifest": {
            "path": "/etc/homelab-stage6/steady-state/homepage.json",
            "sha256": "a04738c432ffd998cb0d17029a0504dc7b3b6782aab4e9057006828b89ae9db0",
        },
        "authority": {
            "repository": "docker-env",
            "revision": "788b302c67fc21618d471ab7951ebf379d2a5593",
            "compose_sha256": "9a1295c5c7848c578a9b339411b02b2320cb7bd4b78764fce1d6b661fe97287f",
            "clean": True,
        },
        "desired": {
            "version": desired_version,
            "configured_image": target["configured_image"],
            "immutable_ref": target["configured_image"],
            "local_image_id": "sha256:3a2b25796deabbf5c77ed9efcca2e1cb270b64f00c70ca87cf797640e26705fe",
        },
        "runtime": {
            "container_id": "d4abcf95abcd187be1f1c21a3e274f7ed924fe1d992fdb6453f9218f710fc88f",
            "restart_count": 0,
            "running": True,
            "networks": ["homelab_apps"],
            "published_ports": [],
            "mounts": [],
        },
        "health": {"strategy": "docker-health", "status": "healthy"},
        "protected_containers": [],
        "mutation_allowed": False,
        "deployment": {"allowed": False, "performed": False},
        "result": "steady-state-verified",
    }


def test_homepage_adapter_without_host_contact() -> None:
    module = load_router_module()
    service, target, desired_version = homepage_target()

    assert target["inspect_ready"] is True
    assert target["steady_state_manifest"] == "homepage.json"
    assert "blocker" not in service["hosts"]["TestServer"]

    evidence = reviewed_homepage_evidence(target, desired_version)
    completed = subprocess.CompletedProcess(
        args=[str(module.STEADY_INSPECTOR), "homepage"],
        returncode=0,
        stdout=json.dumps(evidence),
        stderr="",
    )

    with (
        mock.patch.object(module, "is_installed_mode", return_value=True),
        mock.patch.object(module.os, "geteuid", return_value=0),
        mock.patch.object(module, "current_short_hostname", return_value="TestServer"),
        mock.patch.object(module, "require_secure_regular_file"),
        mock.patch.object(module.subprocess, "run", return_value=completed) as runner,
    ):
        actual = module.execute_local_testserver_inspection(
            "homepage",
            target,
            desired_version,
        )

    assert actual == evidence
    runner.assert_called_once()
    positional, keyword = runner.call_args
    assert positional[0] == [str(module.STEADY_INSPECTOR), "homepage"]
    assert keyword["shell"] is False
    assert keyword["stdin"] is module.subprocess.DEVNULL
    assert keyword["check"] is False
    assert keyword["env"] == module.FIXED_ENV
    print("PASS: Homepage adapter uses fixed argv/no shell under mocked read-only evidence")

    bad = json.loads(json.dumps(evidence))
    bad["mutation_allowed"] = True
    try:
        module.validate_inspection_evidence(
            bad,
            "homepage",
            target,
            desired_version,
        )
    except module.RouterError:
        print("PASS: mutating Homepage evidence -> REJECTED")
    else:
        raise AssertionError("mutating Homepage evidence was accepted")

    with mock.patch.object(module.subprocess, "run") as runner:
        try:
            module.execute_local_testserver_inspection(
                "homepage",
                target,
                desired_version,
            )
        except module.RouterError:
            pass
        else:
            raise AssertionError("source-checkout live inspection gate did not fail closed")
        runner.assert_not_called()
    print("PASS: mutable source checkout cannot perform live host inspection")


def main() -> int:
    prometheus = expect_routing_pass(
        "prometheus default multi-host routing",
        "--service",
        "prometheus",
        "--action",
        "inspect",
    )
    assert [target["host"] for target in prometheus["targets"]] == [
        "TestServer",
        "ids-01",
    ]
    assert prometheus["desired_version"] == "3.13.2"
    assert prometheus["all_targets_inspect_ready"] is False

    blackbox = expect_routing_pass(
        "exact desired version and host filter",
        "--service",
        "blackbox-exporter",
        "--version",
        "0.28.0",
        "--hosts",
        "TestServer",
        "--action",
        "inspect",
    )
    assert len(blackbox["targets"]) == 1
    assert blackbox["targets"][0]["platform"] == "linux/arm64"

    whoami = expect_routing_pass(
        "kubernetes host represented and remains fail-closed",
        "--service",
        "whoami",
        "--action",
        "inspect",
    )
    assert whoami["targets"][0]["host"] == "k3s-node-01"
    assert whoami["targets"][0]["backend"] == "kubernetes-stage6"
    assert whoami["targets"][0]["configured_image"].startswith(
        "traefik/whoami@sha256:"
    )

    test_homepage_adapter_without_host_contact()

    expect_fail(
        "unknown service",
        "--service",
        "not-a-reviewed-service",
        "--action",
        "inspect",
    )
    expect_fail(
        "unknown host",
        "--service",
        "prometheus",
        "--hosts",
        "unknown-host",
        "--action",
        "inspect",
    )
    expect_fail(
        "service not approved on requested host",
        "--service",
        "homepage",
        "--hosts",
        "ids-01",
        "--action",
        "inspect",
    )
    expect_fail(
        "desired-version mismatch",
        "--service",
        "prometheus",
        "--version",
        "3.13.1",
        "--action",
        "inspect",
    )
    expect_fail(
        "caller version without reviewed desired version",
        "--service",
        "alloy",
        "--version",
        "1.19.2",
        "--action",
        "inspect",
    )
    expect_fail(
        "duplicate action",
        "--service",
        "prometheus",
        "--action",
        "inspect",
        "--action",
        "inspect",
    )
    expect_fail(
        "duplicate host in host list",
        "--service",
        "blackbox-exporter",
        "--hosts",
        "TestServer,TestServer",
        "--action",
        "inspect",
    )
    expect_fail(
        "arbitrary image input",
        "--service",
        "prometheus",
        "--action",
        "inspect",
        "--image",
        "evil/image:latest",
    )
    expect_fail(
        "arbitrary compose path input",
        "--service",
        "prometheus",
        "--action",
        "inspect",
        "--compose-file",
        "/tmp/evil.yml",
    )
    expect_fail(
        "arbitrary digest input",
        "--service",
        "prometheus",
        "--action",
        "inspect",
        "--digest",
        "sha256:deadbeef",
    )
    expect_fail(
        "prepare remains fail-closed",
        "--service",
        "prometheus",
        "--action",
        "prepare",
    )
    expect_fail(
        "deploy remains fail-closed",
        "--service",
        "prometheus",
        "--action",
        "deploy",
    )
    expect_fail(
        "rollback remains fail-closed",
        "--service",
        "prometheus",
        "--action",
        "rollback",
    )

    print("PASS: homelab-update Phase 2B source regression suite completed")
    print("NO REAL HOST CONTACT PERFORMED BY REGRESSION SUITE")
    print("NO MUTATION PATH EXISTS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
