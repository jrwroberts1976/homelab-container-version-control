#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WRAPPER = (
    ROOT
    / "ops"
    / "ids01"
    / "homelab-stage6-steady-inspector-ssh"
)

SUDOERS = (
    ROOT
    / "ops"
    / "ids01"
    / "homelab-stage6-steady-inspector-sudoers"
)

KEY_TEMPLATE = (
    ROOT
    / "ops"
    / "ids01"
    / "homelab-stage6-steady-inspector-authorized-key.template"
)

ROUTER = ROOT / "scripts" / "homelab-update.py"
CATALOG = ROOT / "config" / "estate-updater-catalog.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


wrapper = WRAPPER.read_text(encoding="utf-8")
sudoers = SUDOERS.read_text(encoding="utf-8")
key_template = KEY_TEMPLATE.read_text(encoding="utf-8")
router = ROUTER.read_text(encoding="utf-8")
catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

require(
    'COMMAND="${SSH_ORIGINAL_COMMAND:-}"' in wrapper,
    "wrapper must derive command only from SSH_ORIGINAL_COMMAND",
)

require(
    '[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]]' in wrapper,
    "wrapper service grammar missing",
)

require(
    "/usr/local/libexec/homelab-stage6-steady-inspect"
    in wrapper,
    "steady-state inspector dispatch missing",
)

for forbidden in (
    "homelab-stage6-transition",
    "homelab-stage6-execute",
    "docker ",
    "docker-compose",
    "docker compose",
    "git ",
    "scp ",
    "rsync ",
):
    require(
        forbidden not in wrapper,
        f"forbidden wrapper authority present: {forbidden}",
    )

expected_sudo = (
    "homelab-stage6-steady-inspector ALL=(root) NOPASSWD: "
    "/usr/local/libexec/homelab-stage6-steady-inspect "
    "^[a-z0-9][a-z0-9-]*$"
)

require(
    expected_sudo in sudoers,
    "exact steady-state sudo boundary missing",
)

active_sudoers = "\n".join(
    line.split("#", 1)[0].strip()
    for line in sudoers.splitlines()
    if line.split("#", 1)[0].strip()
)

require(
    active_sudoers == expected_sudo,
    "active sudoers content must contain exactly one reviewed rule",
)

for forbidden in (
    "transition",
    "execute",
    "docker",
    "compose",
    "git ",
    "/bin/bash",
    "/bin/sh",
):
    require(
        forbidden not in active_sudoers.lower(),
        f"forbidden active sudo authority present: {forbidden}",
    )

expected_key = (
    'restrict,from="192.168.2.220",'
    'command="/usr/local/sbin/'
    'homelab-stage6-steady-inspector-ssh" '
    'ssh-ed25519 __PUBLIC_KEY__ '
    'homelab-stage6-testserver-ids01-steady-inspector'
)

require(
    key_template.strip() == expected_key,
    "authorized-key template differs from reviewed boundary",
)

host = catalog["hosts"]["ids-01"]

expected_transport = {
    "type": "ssh-fixed-command",
    "address": "192.168.2.242",
    "user": "homelab-stage6-steady-inspector",
    "identity_file":
        "/etc/homelab-stage6/ssh/ids-01-steady-inspector",
    "known_hosts_file":
        "/etc/homelab-stage6/ssh/known_hosts",
}

require(
    host["backend_available"] is True,
    "ids-01 backend not marked available",
)

require(
    host["inspection_transport"] == expected_transport,
    "ids-01 transport differs from exact reviewed metadata",
)

prometheus = catalog["services"]["prometheus"]["hosts"]["ids-01"]

require(
    prometheus["current_version"] == "3.13.2",
    "ids-01 Prometheus current version not updated",
)

require(
    prometheus["configured_image"]
    == (
        "prom/prometheus@sha256:"
        "508729e0e2d18e11fd742a5a5ca70e557b940a93948c3c95fd0123a6fd538b69"
    ),
    "ids-01 configured image differs from verified steady state",
)

require(
    prometheus["coverage"] == "managed-tested",
    "ids-01 coverage not managed-tested",
)

require(
    prometheus["steady_state_manifest"] == "prometheus.json",
    "ids-01 steady-state installed manifest route mismatch",
)

require(
    prometheus["manifest"] == "prometheus-ids01-3.13.2.json",
    "ids-01 transition manifest route mismatch",
)

require(
    prometheus["inspect_ready"] is True,
    "ids-01 Prometheus not inspect-ready",
)

require(
    "blocker" not in prometheus,
    "ids-01 Prometheus still contains onboarding blocker",
)

required_router_tokens = (
    "IDS01_INSPECTION_TRANSPORT",
    "execute_remote_ids01_inspection",
    "execute_reviewed_inspection",
    "StrictHostKeyChecking=yes",
    "BatchMode=yes",
    "IdentitiesOnly=yes",
    "PasswordAuthentication=no",
    "KbdInteractiveAuthentication=no",
    "ClearAllForwardings=yes",
    "PermitLocalCommand=no",
    "GlobalKnownHostsFile=/dev/null",
    "UserKnownHostsFile=",
)

for token in required_router_tokens:
    require(
        token in router,
        f"required router transport control missing: {token}",
    )

for forbidden in (
    "StrictHostKeyChecking=no",
    "PasswordAuthentication=yes",
    "KbdInteractiveAuthentication=yes",
):
    require(
        forbidden not in router,
        f"unsafe SSH router option present: {forbidden}",
    )

require(
    '"--ssh-user"' not in router,
    "caller-controlled SSH user option present",
)

require(
    '"--identity-file"' not in router,
    "caller-controlled identity option present",
)

require(
    '"--ssh-host"' not in router,
    "caller-controlled SSH host option present",
)

print("PASS: ids-01 fixed-command steady inspection transport")
print("NO REAL SSH CONNECTION PERFORMED")
print("NO MUTATION PATH EXPOSED")
