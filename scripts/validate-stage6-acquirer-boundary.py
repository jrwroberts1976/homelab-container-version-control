#!/usr/bin/env python3

from pathlib import Path
import sys


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


root = Path(__file__).resolve().parents[1]

wrapper = root / "ops/testserver/homelab-stage6-acquirer-ssh"
sudoers = root / "ops/testserver/homelab-stage6-acquirer-sudoers"
authkey = root / "ops/testserver/homelab-stage6-acquirer-authorized-key.template"

for path in (wrapper, sudoers, authkey):
    if not path.is_file():
        fail(f"missing required file: {path}")


expected_wrapper = r'''#!/bin/bash
set -euo pipefail

PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

COMMAND="${SSH_ORIGINAL_COMMAND:-}"

fail() {
    printf 'FAIL: command not permitted\n' >&2
    exit 2
}

case "$COMMAND" in
    ping)
        printf 'pong\n'
        ;;
    acquire\ *)
        SERVICE="${COMMAND#acquire }"
        [[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]] || fail

        exec sudo -n \
            /usr/local/libexec/homelab-stage6-candidate-acquire \
            "$SERVICE"
        ;;
    *)
        fail
        ;;
esac
'''

wrapper_text = wrapper.read_text(encoding="utf-8")

if wrapper_text != expected_wrapper:
    fail(
        "acquirer forced-command wrapper differs from the exact reviewed "
        "ping/acquire-only contract"
    )


sudo_code = "\n".join(
    line.strip()
    for line in sudoers.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.strip().startswith("#")
)

expected_sudo = (
    "homelab-stage6-acquirer ALL=(root) NOPASSWD: "
    "/usr/local/libexec/homelab-stage6-candidate-acquire "
    "^[a-z0-9][a-z0-9-]*$"
)

if sudo_code != expected_sudo:
    fail("sudoers boundary is not the single exact reviewed command")


expected_key = (
    'restrict,from="172.30.255.250",'
    'command="/usr/local/sbin/homelab-stage6-acquirer-ssh" '
    'ssh-ed25519 __PUBLIC_KEY__ '
    'homelab-stage6-testserver-acquirer'
)

if authkey.read_text(encoding="utf-8").strip() != expected_key:
    fail("authorized-key template differs from exact restricted form")


print("PASS: Stage 6 acquirer exact SSH/sudo/key boundary")
