#!/usr/bin/env python3

from pathlib import Path
import re
import sys


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


helper_path = Path(
    "ops/testserver/homelab-stage6-authority-inspect"
)

wrapper_path = Path(
    "ops/testserver/homelab-stage6-inspector-ssh"
)

sudoers_path = Path(
    "ops/testserver/homelab-stage6-inspector-sudoers"
)


for path in (
    helper_path,
    wrapper_path,
    sudoers_path,
):
    if not path.is_file():
        fail(f"required source missing: {path}")


helper = helper_path.read_text(encoding="utf-8")
wrapper = wrapper_path.read_text(encoding="utf-8")
sudoers = sudoers_path.read_text(encoding="utf-8")


helper_required = [
    'MANIFEST_DIR="/etc/homelab-stage6/services"',
    'INSTALLED_SELF="/usr/local/libexec/homelab-stage6-authority-inspect"',
    'CANDIDATE_ACQUIRE="/usr/local/libexec/homelab-stage6-candidate-acquire"',
    'VALIDATOR="/usr/local/libexec/homelab-stage6-validate-service-manifest"',
    'INSPECTOR="/usr/local/libexec/homelab-stage6-inspect"',
    'ACQUIRER_WRAPPER="/usr/local/sbin/homelab-stage6-acquirer-ssh"',
    'INSPECTOR_WRAPPER="/usr/local/sbin/homelab-stage6-inspector-ssh"',
    '"$VALIDATOR" "$MANIFEST" >/dev/null',
    'artifact: "stage6-live-authority"',
    'result: "live-authority-inspected"',
    "manifest_sha256",
    "authority_inspector_sha256",
    "candidate_acquire_sha256",
    "service_validator_sha256",
    "inspector_sha256",
    "acquirer_wrapper_sha256",
    "inspector_wrapper_sha256",
]

for needle in helper_required:
    if needle not in helper:
        fail(
            "authority helper invariant missing: "
            f"{needle}"
        )


mutation_patterns = [
    (
        "mutating docker command",
        re.compile(
            r"^[ \t]*(?:sudo[ \t]+)?"
            r"docker[ \t]+"
            r"(?:pull|compose|run|create|rm|restart|stop|start)"
            r"\b",
            re.MULTILINE,
        ),
    ),
    (
        "host/service mutation command",
        re.compile(
            r"^[ \t]*(?:sudo[ \t]+)?"
            r"(?:systemctl|service|chmod|chown|install|rm|mv|cp)"
            r"[ \t]+",
            re.MULTILINE,
        ),
    ),
]

for label, pattern in mutation_patterns:
    match = pattern.search(helper)

    if match is not None:
        line = helper.count(
            "\n",
            0,
            match.start(),
        ) + 1

        fail(
            f"{label} found on source line {line}: "
            f"{match.group(0).strip()}"
        )


wrapper_required = [
    "authority\\ *)",
    'SERVICE="${COMMAND#authority }"',
    '[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]]',
    'exec sudo -n /usr/local/libexec/'
    'homelab-stage6-authority-inspect "$SERVICE"',
]

for needle in wrapper_required:
    if needle not in wrapper:
        fail(
            "inspector SSH authority boundary missing: "
            f"{needle}"
        )


sudoers_required = (
    "homelab-stage6-inspector ALL=(root) NOPASSWD: "
    "/usr/local/libexec/homelab-stage6-authority-inspect "
    "^[a-z0-9][a-z0-9-]*$"
)

if sudoers_required not in sudoers:
    fail(
        "inspector sudo authority boundary missing"
    )


print(
    "PASS: Stage 6 live-authority read-only boundary"
)
