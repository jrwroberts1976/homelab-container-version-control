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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inspector", type=Path)
    args = parser.parse_args()

    text = args.inspector.read_text(encoding="utf-8")
    code_lines = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        code_lines.append(line)

    code_text = "\n".join(code_lines)
    normalized = re.sub(r"\\\s*\n\s*", " ", code_text)
    normalized = re.sub(r"[ \t]+", " ", normalized)

    required = [
        'MANIFEST_DIR="/etc/homelab-stage6/services"',
        'VALIDATOR="/usr/local/libexec/homelab-stage6-validate-service-manifest"',
        'INSTALLED_SELF="/usr/local/libexec/homelab-stage6-inspect"',
        'AUTHORITY_ROOT="/var/lib/homelab-stage6/authority/docker-env"',
        'LIVE_ROOT="/home/james/docker"',
        '[ "$#" -eq 1 ]',
        '[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]]',
        'MANIFEST="${MANIFEST_DIR}/${SERVICE}.json"',
        'git -C "$AUTHORITY_ROOT" rev-parse HEAD',
        'git -C "$AUTHORITY_ROOT" status --porcelain',
        'verify_hash "$AUTHORITY_COMPOSE" "$expected_sha"',
        'verify_hash "$COMPOSE_FILE" "$expected_sha"',
        'verify_local_images',
        'verify_runtime_shape',
        'verify_health',
        'CONTAINER_STATE="$(build_container_state)"',
        'result: "ready-for-human-review"',
        'allowed: false',
        'performed: false',
    ]

    for needle in required:
        require(needle in text, f"required inspector invariant missing: {needle}")

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
        require(needle not in normalized, f"banned inspector operation present: {needle}")

    compose_count = normalized.count("docker compose ")
    require(
        compose_count == 2,
        f"expected exactly two read-only docker compose invocations, found {compose_count}",
    )

    compose_segments = normalized.split("docker compose ")[1:]
    for segment in compose_segments:
        command = segment.split("\n", 1)[0]
        require(" config" in command, f"Compose invocation is not config-only: {command}")

    docker_mutation_words = re.compile(
        r"\bdocker\s+(pull|run|create|start|restart|stop|rm|kill|exec|tag|rmi)\b"
    )
    require(
        docker_mutation_words.search(normalized) is None,
        "mutating Docker command present",
    )

    require('SERVICE="$1"' in text, "service must come only from first positional argument")
    require(
        'SERVICE="$2"' not in code_text and 'SERVICE="${2' not in code_text,
        "service must not use second positional argument",
    )

    print("PASS: Stage 6 generic inspector source guard")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
