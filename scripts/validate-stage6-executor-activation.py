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
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-transition ^arm [a-z0-9][a-z0-9-]*$",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-transition ^disarm [a-z0-9][a-z0-9-]*$",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-execute ^deploy [a-z0-9][a-z0-9-]*$",
        "homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-execute ^rollback [a-z0-9][a-z0-9-]*$",
    ]
    require(
        lines == expected,
        "sudoers boundary must contain exactly four generic action/service regex commands",
    )

    text = path.read_text(encoding="utf-8")
    significant = "\n".join(lines)

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
    require("dashy" not in significant and "prometheus" not in significant, "sudoers must not hard-code services")


def validate_authorized_key_template(path: Path) -> None:
    lines = significant_lines(path)
    require(len(lines) == 1, "authorized-key template must contain exactly one significant line")
    expected = 'restrict,from="172.30.255.250",command="/usr/local/sbin/homelab-stage6-executor-ssh" ssh-ed25519 __PUBLIC_KEY__ homelab-stage6-testserver-executor'
    require(lines[0] == expected, "authorized-key template differs from exact source-restricted forced-command contract")
    require(lines[0].count("__PUBLIC_KEY__") == 1, "authorized-key template must contain exactly one public-key placeholder")
    require("PRIVATE" not in lines[0].upper(), "authorized-key template must never contain private-key material")


def validate_wrapper(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    required = [
        'COMMAND="${SSH_ORIGINAL_COMMAND:-}"',
        'require_service() {',
        '[[ "$service" =~ ^[a-z0-9][a-z0-9-]*$ ]] || fail',
        'arm\\ *|disarm\\ *)',
        'deploy\\ *|rollback\\ *)',
        'ACTION="${COMMAND%% *}"',
        'SERVICE="${COMMAND#* }"',
        'require_service "$SERVICE"',
        'exec sudo -n /usr/local/libexec/homelab-stage6-transition "$ACTION" "$SERVICE"',
        'exec sudo -n /usr/local/libexec/homelab-stage6-execute "$ACTION" "$SERVICE"',
        'FAIL: command not permitted',
    ]
    for token in required:
        require(token in text, f"wrapper requirement missing: {token}")

    require("dashy" not in text.lower() and "prometheus" not in text.lower(), "wrapper must not hard-code services")
    require("docker " not in text.lower(), "executor wrapper must not call Docker directly")
    require("git " not in text.lower(), "executor wrapper must not call Git directly")
    require("eval " not in text.lower(), "executor wrapper must not use eval")
    require("bash -c" not in text.lower() and "sh -c" not in text.lower(), "executor wrapper must not spawn arbitrary shell commands")

    sudo_lines = [line.strip() for line in text.splitlines() if "exec sudo -n" in line]
    expected_sudo_lines = [
        'exec sudo -n /usr/local/libexec/homelab-stage6-transition "$ACTION" "$SERVICE"',
        'exec sudo -n /usr/local/libexec/homelab-stage6-execute "$ACTION" "$SERVICE"',
    ]
    require(
        sudo_lines == expected_sudo_lines,
        "wrapper must expose exactly the generic transition and execution helpers",
    )

    transition_case = text[text.find('arm\\ *|disarm\\ *)') : text.find('deploy\\ *|rollback\\ *)')]
    require('require_service "$SERVICE"' in transition_case, "transition service validation missing")
    require(
        transition_case.find('require_service "$SERVICE"')
        < transition_case.find('exec sudo -n /usr/local/libexec/homelab-stage6-transition'),
        "transition service validation must precede sudo",
    )

    execute_case = text[text.find('deploy\\ *|rollback\\ *)') : text.find('*)', text.find('deploy\\ *|rollback\\ *)'))]
    require('require_service "$SERVICE"' in execute_case, "execution service validation missing")
    require(
        execute_case.find('require_service "$SERVICE"')
        < execute_case.find('exec sudo -n /usr/local/libexec/homelab-stage6-execute'),
        "execution service validation must precede sudo",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sudoers", type=Path)
    parser.add_argument("authorized_key_template", type=Path)
    parser.add_argument("wrapper", type=Path)
    args = parser.parse_args()

    validate_sudoers(args.sudoers)
    validate_authorized_key_template(args.authorized_key_template)
    validate_wrapper(args.wrapper)

    print("PASS: Stage 6 generic executor activation source guard")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
