#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTER = ROOT / "scripts" / "homelab-update.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROUTER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def expect_pass(name: str, *args: str) -> dict:
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


def main() -> int:
    prometheus = expect_pass(
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

    blackbox = expect_pass(
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

    whoami = expect_pass(
        "kubernetes host represented from day one",
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

    homepage = expect_pass(
        "managed Homepage resolves current reviewed manifest",
        "--service",
        "homepage",
        "--action",
        "inspect",
    )
    assert homepage["all_targets_inspect_ready"] is True
    assert homepage["targets"][0]["manifest"] == "homepage-2.1.2.json"

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

    print("PASS: homelab-update Phase 1 router regression suite completed")
    print("NO HOST CONTACT PERFORMED")
    print("NO MUTATION PATH EXISTS IN PHASE 1 ROUTER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
