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
    code_lines = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        code_lines.append(line)

    code_text = "\n".join(code_lines)

    required = [
        'MANIFEST_DIR="/etc/homelab-stage6/services"',
        'VALIDATOR="/usr/local/libexec/homelab-stage6-validate-service-manifest"',
        '[ "$#" -eq 1 ]',
        '[[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]]',
        'MANIFEST="${MANIFEST_DIR}/${SERVICE}.json"',
        'CANDIDATE_LOCAL_REQUIRED="$(jq -r \' .execution.candidate_must_be_local_before_arm\' "$MANIFEST")"'.replace("' .", "'."),
        'DEPLOYMENT_PULL_ALLOWED="$(jq -r \' .execution.deployment_pull_allowed\' "$MANIFEST")"'.replace("' .", "'."),
        '[ "$CANDIDATE_LOCAL_REQUIRED" = "true" ]',
        '[ "$DEPLOYMENT_PULL_ALLOWED" = "false" ]',
        'docker pull "$IMMUTABLE_REF"',
        '[ "$LOCAL_ID" = "$CONFIG_DIGEST" ]',
        '[ "$BEFORE_CONTAINERS" = "$AFTER_CONTAINERS" ]',
        'container_mutation_performed: false',
    ]

    for needle in required:
        require(needle in text, f"required acquisition invariant missing: {needle}")

    # jq -e returns non-zero when a valid JSON boolean is false. Boolean policy
    # fields must therefore be read with plain -r and checked explicitly.
    forbidden_boolean_reads = [
        "jq -er '.execution.candidate_must_be_local_before_arm'",
        "jq -er '.execution.deployment_pull_allowed'",
        "jq -e -r '.execution.candidate_must_be_local_before_arm'",
        "jq -e -r '.execution.deployment_pull_allowed'",
    ]
    for needle in forbidden_boolean_reads:
        require(needle not in code_text, f"boolean policy must not use jq -e: {needle}")

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
        require(needle not in code_text, f"banned executable operation present: {needle}")

    # The only permitted mutating Docker command in the helper is one exact
    # manifest-derived pull. Inspect/ps/image inspect are read-only.
    docker_lines = [
        line for line in code_lines
        if re.search(r"(^|\s)docker\s+", line)
    ]

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

    # Reject extra positional-argument expansion. SERVICE is the only caller
    # input and may select only a fixed root-owned manifest basename.
    require("$2" not in code_text and "${2" not in code_text, "second positional argument not allowed")
    require("$3" not in code_text and "${3" not in code_text, "third positional argument not allowed")

    print("PASS: Stage 6 candidate acquisition source guard")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
