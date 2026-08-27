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
    parser.add_argument("helper", type=Path)
    args = parser.parse_args()

    text = args.helper.read_text(encoding="utf-8")

    required = [
        'MANIFEST_DIR="/etc/homelab-stage6/services"',
        'VALIDATOR="/usr/local/libexec/homelab-stage6-validate-service-manifest"',
        '[ "$#" -eq 1 ]',
        '[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]]',
        'MANIFEST="${MANIFEST_DIR}/${SERVICE}.json"',
        'docker pull "$IMMUTABLE_REF"',
        '[ "$LOCAL_ID" = "$CONFIG_DIGEST" ]',
        '[ "$BEFORE_CONTAINERS" = "$AFTER_CONTAINERS" ]',
        'container_mutation_performed: false',
    ]

    for needle in required:
        require(needle in text, f"required acquisition invariant missing: {needle}")

    banned_literal = [
        "docker compose",
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
        "eval ",
        "bash -c",
        "sh -c",
        ":latest",
    ]

    for needle in banned_literal:
        require(needle not in text, f"banned operation present: {needle}")

    # The only permitted mutating Docker command in the helper is one exact
    # manifest-derived pull. Inspect/ps/image inspect are read-only.
    docker_lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.search(r"(^|\s)docker\s+", line):
            docker_lines.append(line)

    pulls = [line for line in docker_lines if "docker pull" in line]
    require(len(pulls) == 1, f"expected exactly one docker pull, found {len(pulls)}")
    require(pulls[0] == 'docker pull "$IMMUTABLE_REF" >/dev/null', "docker pull must use exact manifest-derived immutable ref")

    for line in docker_lines:
        allowed = (
            "docker ps " in line
            or "docker inspect " in line
            or "docker image inspect " in line
            or line == 'docker pull "$IMMUTABLE_REF" >/dev/null'
        )
        require(allowed, f"unexpected Docker command surface: {line}")

    # Reject extra positional-argument expansion into Docker or filesystem
    # paths. SERVICE is the only caller input and may select only a fixed
    # root-owned manifest basename.
    require("$2" not in text and "${2" not in text, "second positional argument not allowed")
    require("$3" not in text and "${3" not in text, "third positional argument not allowed")

    print("PASS: Stage 6 candidate acquisition source guard")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
