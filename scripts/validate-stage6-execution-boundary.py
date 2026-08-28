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


def normalize(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    code_lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        code_lines.append(line)
    code_text = "\n".join(code_lines)
    normalized = re.sub(r"\\\s*\n\s*", " ", code_text)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return text, normalized


def require_order(text: str, needles: list[str], label: str) -> None:
    positions = []
    for needle in needles:
        position = text.find(needle)
        require(position >= 0, f"{label} ordering token missing: {needle}")
        positions.append(position)
    require(positions == sorted(positions), f"{label} ordering is incorrect")


def validate_transition(path: Path) -> None:
    text, normalized = normalize(path)

    required = [
        'MANIFEST_DIR="/etc/homelab-stage6/services"',
        'VALIDATOR="/usr/local/libexec/homelab-stage6-validate-service-manifest"',
        'INSPECTOR="/usr/local/libexec/homelab-stage6-inspect"',
        'EXECUTOR_HELPER="/usr/local/libexec/homelab-stage6-execute"',
        'INSTALLED_SELF="/usr/local/libexec/homelab-stage6-transition"',
        'STATE_ROOT="/var/lib/homelab-stage6/state"',
        '[ "$#" -eq 2 ]',
        'ACTION="$1"',
        'SERVICE="$2"',
        '[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]]',
        'UPDATE_ID="stage6-${SERVICE}-${CANDIDATE_INDEX_DIGEST#sha256:}"',
        '[ ! -e "$ENABLE_FILE" ]',
        '[ ! -e "$CONSUMED_FILE" ]',
        'run_preapproval_inspection',
        'deployment_authority: true',
        'deployment_authority: false',
    ]
    for needle in required:
        require(needle in text, f"transition invariant missing: {needle}")

    banned = [
        "docker pull",
        "docker run",
        "docker create",
        "docker start",
        "docker restart",
        "docker stop",
        "docker rm",
        "docker kill",
        "docker exec",
        "docker tag",
        "docker rmi",
        "docker compose up",
        "docker compose down",
        "docker compose pull",
        "docker compose build",
        "git fetch",
        "git pull",
        "git reset",
        "git checkout",
        "git clean",
        "sudo ",
        "eval ",
        "bash -c",
        "sh -c",
        ":latest",
    ]
    for needle in banned:
        require(needle not in normalized, f"transition banned operation present: {needle}")

    require('case "$ACTION" in' in text, "transition action case missing")
    require("arm)" in text and "disarm)" in text, "transition must expose only arm/disarm cases")
    require('SERVICE="$3"' not in text and '${3' not in text, "transition must not accept a third argument")
    require('rm -f "$CONSUMED_FILE"' not in text, "transition must never delete consumed evidence")

    arm_text = text[text.find("arm() {") : text.find("disarm() {")]
    require_order(
        arm_text,
        [
            '[ ! -e "$CONSUMED_FILE" ]',
            "run_preapproval_inspection",
            'mv -f "$tmp" "$ENABLE_FILE"',
        ],
        "arm",
    )


def validate_execute(path: Path) -> None:
    text, normalized = normalize(path)

    required = [
        'MANIFEST_DIR="/etc/homelab-stage6/services"',
        'VALIDATOR="/usr/local/libexec/homelab-stage6-validate-service-manifest"',
        'INSPECTOR="/usr/local/libexec/homelab-stage6-inspect"',
        'INSTALLED_SELF="/usr/local/libexec/homelab-stage6-execute"',
        'AUTHORITY_ROOT="/var/lib/homelab-stage6/authority/docker-env"',
        'LIVE_ROOT="/home/james/docker"',
        'STATE_ROOT="/var/lib/homelab-stage6/state"',
        '[ "$#" -eq 2 ]',
        'ACTION="$1"',
        'SERVICE="$2"',
        '[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]]',
        'UPDATE_ID="stage6-${SERVICE}-${CANDIDATE_INDEX_DIGEST#sha256:}"',
        'require_armed',
        'verify_git_authority',
        'verify_local_images',
        'run_predeployment_inspection',
        'mark_consumed',
        'verify_unrelated_unchanged',
        '--no-deps',
        '--no-build',
        '--pull never',
        '--force-recreate',
        'container_mutation_performed: true',
        'unrelated_containers_unchanged: true',
        'deployment_authority_remains_armed: true',
    ]
    for needle in required:
        require(needle in text, f"execution invariant missing: {needle}")

    banned = [
        "docker pull",
        "docker run",
        "docker create",
        "docker start",
        "docker restart",
        "docker stop",
        "docker rm",
        "docker kill",
        "docker exec",
        "docker tag",
        "docker rmi",
        "docker system prune",
        "docker image prune",
        "docker container prune",
        "docker compose down",
        "docker compose pull",
        "docker compose build",
        "git fetch",
        "git pull",
        "git reset",
        "git checkout",
        "git clean",
        "sudo ",
        "eval ",
        "bash -c",
        "sh -c",
        ":latest",
    ]
    for needle in banned:
        require(needle not in normalized, f"execution banned operation present: {needle}")

    compose_count = normalized.count("docker compose ")
    require(compose_count == 1, f"expected one internally constructed Compose lifecycle command, found {compose_count}")
    require(" up -d " in normalized, "Compose command must use up -d")
    require('env "$IMAGE_VARIABLE=$image"' in text, "Compose image must come only from manifest-derived helper parameter")
    require('compose_recreate "$CANDIDATE_REF"' in text, "deploy must use exact manifest candidate ref")
    require('compose_recreate "$ROLLBACK_REF"' in text, "rollback must use exact manifest rollback ref")
    require('SERVICE="$3"' not in text and '${3' not in text, "execution helper must not accept a third argument")
    require('case "$ACTION" in' in text, "execution action case missing")
    require("deploy)" in text and "rollback)" in text, "execution helper must expose deploy/rollback cases")
    require('rm -f "$CONSUMED_FILE"' not in text, "execution helper must never delete consumed evidence")

    deploy_text = text[text.find("deploy() {") : text.find("rollback() {")]
    require_order(
        deploy_text,
        [
            "run_predeployment_inspection",
            'before="$(build_container_state)"',
            "mark_consumed",
            'compose_recreate "$CANDIDATE_REF"',
            'verify_runtime_shape "$CANDIDATE_CONFIG_DIGEST" "$CANDIDATE_REF"',
            "wait_for_health",
            'after="$(build_container_state)"',
            'verify_unrelated_unchanged "$before" "$after"',
        ],
        "deploy",
    )

    rollback_start = text.find("rollback() {")
    require(rollback_start >= 0, "rollback function missing")
    rollback_end = text.find('[ "$(id -u)"', rollback_start)
    require(rollback_end > rollback_start, "rollback function end marker missing")
    rollback_text = text[rollback_start:rollback_end]
    require_order(
        rollback_text,
        [
            'require_secure_root_file "$CONSUMED_FILE"',
            "verify_git_authority",
            "verify_local_images",
            '[ "$current_image" = "$CANDIDATE_CONFIG_DIGEST" ]',
            'verify_runtime_shape "$CANDIDATE_CONFIG_DIGEST" "$CANDIDATE_REF"',
            'before="$(build_container_state)"',
            'compose_recreate "$ROLLBACK_REF"',
            'verify_runtime_shape "$ROLLBACK_LOCAL_ID" "$ROLLBACK_REF"',
            "wait_for_health",
            'after="$(build_container_state)"',
            'verify_unrelated_unchanged "$before" "$after"',
        ],
        "rollback",
    )


def validate_wrapper(path: Path) -> None:
    text, normalized = normalize(path)

    required = [
        'COMMAND="${SSH_ORIGINAL_COMMAND:-}"',
        '"arm dashy")',
        'exec sudo -n /usr/local/libexec/homelab-stage6-transition arm dashy',
        '"deploy dashy")',
        'exec sudo -n /usr/local/libexec/homelab-stage6-execute deploy dashy',
        '"rollback dashy")',
        'exec sudo -n /usr/local/libexec/homelab-stage6-execute rollback dashy',
        '"disarm dashy")',
        'exec sudo -n /usr/local/libexec/homelab-stage6-transition disarm dashy',
        '"arm prometheus")',
        'exec sudo -n /usr/local/libexec/homelab-stage6-transition arm prometheus',
        '"deploy prometheus")',
        'exec sudo -n /usr/local/libexec/homelab-stage6-execute deploy prometheus',
        '"rollback prometheus")',
        'exec sudo -n /usr/local/libexec/homelab-stage6-execute rollback prometheus',
        '"disarm prometheus")',
        'exec sudo -n /usr/local/libexec/homelab-stage6-transition disarm prometheus',
        'FAIL: command not permitted',
    ]
    for needle in required:
        require(needle in text, f"executor wrapper invariant missing: {needle}")

    require("$SERVICE" not in text, "executor wrapper must not accept variable service selection")
    require("$ACTION" not in text, "executor wrapper must not accept variable action selection")
    require("docker " not in normalized, "executor wrapper must not call Docker directly")
    require("git " not in normalized, "executor wrapper must not call Git directly")
    require("eval " not in normalized, "executor wrapper must not use eval")
    require("bash -c" not in normalized and "sh -c" not in normalized, "executor wrapper must not spawn arbitrary shell commands")

    sudo_lines = [line.strip() for line in text.splitlines() if "exec sudo -n" in line]

    expected_sudo_lines = [
        "exec sudo -n /usr/local/libexec/homelab-stage6-transition arm dashy",
        "exec sudo -n /usr/local/libexec/homelab-stage6-execute deploy dashy",
        "exec sudo -n /usr/local/libexec/homelab-stage6-execute rollback dashy",
        "exec sudo -n /usr/local/libexec/homelab-stage6-transition disarm dashy",
        "exec sudo -n /usr/local/libexec/homelab-stage6-transition arm prometheus",
        "exec sudo -n /usr/local/libexec/homelab-stage6-execute deploy prometheus",
        "exec sudo -n /usr/local/libexec/homelab-stage6-execute rollback prometheus",
        "exec sudo -n /usr/local/libexec/homelab-stage6-transition disarm prometheus",
    ]

    require(
        sudo_lines == expected_sudo_lines,
        "executor wrapper sudo surface must be exactly Dashy and Prometheus",
    )

    for line in sudo_lines:
        require(
            "$" not in line,
            f"executor sudo line contains variable expansion: {line}",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("transition", type=Path)
    parser.add_argument("execute", type=Path)
    parser.add_argument("wrapper", type=Path)
    args = parser.parse_args()

    validate_transition(args.transition)
    validate_execute(args.execute)
    validate_wrapper(args.wrapper)

    print("PASS: Stage 6 generic execution boundary source guard")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
