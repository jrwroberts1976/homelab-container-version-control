#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def significant_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def validate_sudoers(path: Path) -> None:
    lines = significant_lines(path)
    expected = [
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-transition arm dashy",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-execute deploy dashy",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-execute rollback dashy",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-transition disarm dashy",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-transition arm prometheus",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-execute deploy prometheus",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-execute rollback prometheus",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-transition disarm prometheus",
    ]
    require(
        lines == expected,
        "sudoers boundary must contain exactly eight literal Dashy/Prometheus commands",
    )

    text = path.read_text(encoding="utf-8")
    significant = "\n".join(lines)

    for token in ("*", "?", "[", "]", "$", "`", "\\"):
        require(token not in significant, f"sudoers boundary contains forbidden metacharacter: {token}")

    forbidden_command = re.compile(
        r"(?:^|[\s,:])(?:/usr/bin/|/bin/)?(?:sh|bash|docker|compose|git|cp|mv|rm|tee|vi|vim|nano)(?=\s|$)"
    )
    match = forbidden_command.search(significant)
    require(
        match is None,
        f"sudoers boundary contains forbidden command token: {match.group(0).strip() if match else ''}",
    )

    require("NOPASSWD: ALL" not in text, "sudoers must not grant NOPASSWD: ALL")
    require("(ALL" not in text, "sudoers runas target must remain root only")


def validate_authorized_key_template(path: Path) -> None:
    lines = significant_lines(path)
    require(len(lines) == 1, "authorized-key template must contain exactly one significant line")
    expected = 'restrict,from="172.30.255.250",command="/usr/local/sbin/homelab-stage6-executor-ssh" ssh-ed25519 __PUBLIC_KEY__ homelab-stage6-testserver-executor'
    require(lines[0] == expected, "authorized-key template differs from exact source-restricted forced-command contract")
    require(lines[0].count("__PUBLIC_KEY__") == 1, "authorized-key template must contain exactly one public-key placeholder")
    require("PRIVATE" not in lines[0].upper(), "authorized-key template must never contain private-key material")


def validate_wrapper(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    expected_commands = [
        ('"arm dashy")', "exec sudo -n /usr/local/libexec/homelab-stage6-transition arm dashy"),
        ('"deploy dashy")', "exec sudo -n /usr/local/libexec/homelab-stage6-execute deploy dashy"),
        ('"rollback dashy")', "exec sudo -n /usr/local/libexec/homelab-stage6-execute rollback dashy"),
        ('"disarm dashy")', "exec sudo -n /usr/local/libexec/homelab-stage6-transition disarm dashy"),
        ('"arm prometheus")', "exec sudo -n /usr/local/libexec/homelab-stage6-transition arm prometheus"),
        ('"deploy prometheus")', "exec sudo -n /usr/local/libexec/homelab-stage6-execute deploy prometheus"),
        ('"rollback prometheus")', "exec sudo -n /usr/local/libexec/homelab-stage6-execute rollback prometheus"),
        ('"disarm prometheus")', "exec sudo -n /usr/local/libexec/homelab-stage6-transition disarm prometheus"),
    ]
    for case_token, sudo_token in expected_commands:
        require(case_token in text, f"wrapper literal case missing: {case_token}")
        require(sudo_token in text, f"wrapper literal sudo line missing: {sudo_token}")

    sudo_lines = [line.strip() for line in text.splitlines() if "exec sudo -n" in line]
    expected_sudo_lines = [sudo_token for _, sudo_token in expected_commands]

    require(
        sudo_lines == expected_sudo_lines,
        "wrapper must expose exactly the reviewed Dashy/Prometheus sudo lines",
    )

    for line in sudo_lines:
        require(
            "$" not in line,
            f"wrapper sudo line contains variable expansion: {line}",
        )

    require('COMMAND="${SSH_ORIGINAL_COMMAND:-}"' in text, "wrapper must dispatch only SSH_ORIGINAL_COMMAND")
    require('FAIL: command not permitted' in text, "wrapper default rejection missing")
    require("$SERVICE" not in text and "$ACTION" not in text, "wrapper must not accept variable service/action selection")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sudoers", type=Path)
    parser.add_argument("authorized_key_template", type=Path)
    parser.add_argument("wrapper", type=Path)
    args = parser.parse_args()

    validate_sudoers(args.sudoers)
    validate_authorized_key_template(args.authorized_key_template)
    validate_wrapper(args.wrapper)

    print("PASS: Stage 6 executor activation source guard")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
