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
    '"inspect dashy")',
    'exec sudo -n /usr/local/libexec/homelab-stage6-inspect dashy',
    "printf 'FAIL: command not permitted\\n' >&2",
]
for token in required_wrapper:
    if token not in wrapper:
        fail(f"wrapper requirement missing: {token}")

sudo_lines = [line.strip() for line in sudoers.splitlines() if line.strip() and not line.lstrip().startswith('#')]
expected_sudo = [
    'homelab-stage6-inspector ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-inspect dashy'
]
if sudo_lines != expected_sudo:
    fail("sudoers must contain exactly one literal Dashy inspection command")

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

# The wrapper may invoke sudo only once, for the exact read-only inspector command.
sudo_calls = re.findall(r'\bsudo\b[^\n]*', wrapper)
if sudo_calls != ['sudo -n /usr/local/libexec/homelab-stage6-inspect dashy']:
    fail("wrapper sudo surface is not exactly one read-only Dashy inspection command")

# Do not permit execution actions or variable service forwarding.
for forbidden in ('arm dashy', 'deploy dashy', 'rollback dashy', 'disarm dashy', '$SERVICE', '${SERVICE'):
    if forbidden in wrapper or forbidden in sudoers:
        fail(f"execution/service-variable authority present: {forbidden}")

print('PASS: Stage 6 inspector transport source guard')
