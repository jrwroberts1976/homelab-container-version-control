#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(2)


if len(sys.argv) != 4:
    fail("usage: validate-stage6-inspector-transport.py WRAPPER SUDOERS AUTHKEY_TEMPLATE")

wrapper_path = pathlib.Path(sys.argv[1])
sudoers_path = pathlib.Path(sys.argv[2])
authkey_path = pathlib.Path(sys.argv[3])

for path in (wrapper_path, sudoers_path, authkey_path):
    if not path.is_file():
        fail(f"missing source file: {path}")

wrapper = wrapper_path.read_text()
sudoers = sudoers_path.read_text()
authkey = authkey_path.read_text()

required_wrapper = [
    'COMMAND="${SSH_ORIGINAL_COMMAND:-}"',
    'ping)',
    'inspect\\ *)',
    'SERVICE="${COMMAND#inspect }"',
    '[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]] || fail',
    'exec sudo -n /usr/local/libexec/homelab-stage6-inspect "$SERVICE"',
    "printf 'FAIL: command not permitted\\n' >&2",
]
for token in required_wrapper:
    if token not in wrapper:
        fail(f"wrapper requirement missing: {token}")

validation_pos = wrapper.find('[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]] || fail')
sudo_pos = wrapper.find('exec sudo -n /usr/local/libexec/homelab-stage6-inspect "$SERVICE"')
if validation_pos < 0 or sudo_pos < 0 or validation_pos > sudo_pos:
    fail("service identifier must be validated before sudo dispatch")

sudo_lines = [
    line.strip()
    for line in sudoers.splitlines()
    if line.strip() and not line.lstrip().startswith('#')
]
expected_sudo = [
    'homelab-stage6-inspector ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-inspect ^[a-z0-9][a-z0-9-]*$',
]
if sudo_lines != expected_sudo:
    fail("sudoers must contain exactly the generic manifest-driven inspection regex")

expected_authkey = (
    'restrict,from="172.30.255.250",command="/usr/local/sbin/homelab-stage6-inspector-ssh" '
    'ssh-ed25519 __PUBLIC_KEY__ homelab-stage6-testserver-inspector\n'
)
if authkey != expected_authkey:
    fail("authorized-key template is not exact")

if authkey.count('__PUBLIC_KEY__') != 1:
    fail("authorized-key template must contain exactly one public-key placeholder")

for text, label in ((wrapper, 'wrapper'), (sudoers, 'sudoers'), (authkey, 'authorized-key template')):
    lowered = text.lower()
    for forbidden in (
        'docker ', 'docker\t', ' compose ', 'git ', 'bash -c', 'sh -c', 'eval ',
        'nopasswd: all', ':latest', 'curl ', 'wget ', 'scp ', 'rsync ', 'tee ',
    ):
        if forbidden in lowered:
            fail(f"{label} contains forbidden token: {forbidden.strip()}")

for service_literal in ('dashy', 'prometheus'):
    if service_literal in wrapper.lower() or service_literal in sudoers.lower():
        fail(f"transport must not hard-code onboarded service: {service_literal}")

# The wrapper may invoke sudo only through the generic root-owned read-only inspector.
sudo_calls = re.findall(r'\bsudo\b[^\n]*', wrapper)
expected_sudo_calls = [
    'sudo -n /usr/local/libexec/homelab-stage6-inspect "$SERVICE"',
]
if sudo_calls != expected_sudo_calls:
    fail("wrapper sudo surface is not exactly the generic Stage 6 inspector")

# The inspector identity must never receive execution authority.
for forbidden in (
    '/usr/local/libexec/homelab-stage6-transition',
    '/usr/local/libexec/homelab-stage6-execute',
    ' arm ',
    ' deploy ',
    ' rollback ',
    ' disarm ',
):
    if forbidden in wrapper or forbidden in sudoers:
        fail(f"execution authority present: {forbidden}")

print('PASS: Stage 6 generic inspector transport source guard')
