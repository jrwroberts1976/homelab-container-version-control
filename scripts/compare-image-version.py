#!/usr/bin/env python3

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = PROJECT_ROOT / "config" / "version-schemes.yml"

DIGEST_RE = re.compile(
    r"^sha256:[0-9a-f]{64}$"
)

SEMVER_RE = re.compile(
    r"^v?"
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read-only container image version comparator."
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Version scheme registry.",
    )
    parser.add_argument(
        "--image-type",
        choices=("registry-image", "local-build"),
        default="registry-image",
    )
    parser.add_argument("current")
    parser.add_argument("candidate")
    return parser.parse_args()


def split_reference(reference):
    digest = None
    base = reference

    if "@" in reference:
        base, digest = reference.rsplit("@", 1)
        digest = digest.lower()

        if not DIGEST_RE.fullmatch(digest):
            raise SystemExit(
                f"ERROR: invalid SHA-256 image digest: {digest}"
            )

    last_slash = base.rfind("/")
    last_colon = base.rfind(":")

    if last_colon > last_slash:
        repository = base[:last_colon]
        tag = base[last_colon + 1 :]
    else:
        repository = base
        tag = None

    return {
        "reference": reference,
        "repository": repository,
        "tag": tag,
        "digest": digest,
    }


def parse_semver(value):
    match = SEMVER_RE.fullmatch(value or "")

    if not match:
        return None

    major, minor, patch, prerelease = match.groups()

    return (
        int(major),
        int(minor),
        int(patch),
        prerelease,
    )


def compare_prerelease(left, right):
    if left is None and right is None:
        return 0

    if left is None:
        return 1

    if right is None:
        return -1

    left_parts = left.split(".")
    right_parts = right.split(".")

    for left_part, right_part in zip(left_parts, right_parts):
        if left_part == right_part:
            continue

        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()

        if left_numeric and right_numeric:
            return (int(left_part) > int(right_part)) - (
                int(left_part) < int(right_part)
            )

        if left_numeric and not right_numeric:
            return -1

        if not left_numeric and right_numeric:
            return 1

        return (left_part > right_part) - (left_part < right_part)

    return (len(left_parts) > len(right_parts)) - (
        len(left_parts) < len(right_parts)
    )


def compare_semver(current, candidate):
    left = parse_semver(current)
    right = parse_semver(candidate)

    if left is None or right is None:
        return None

    left_core = left[:3]
    right_core = right[:3]

    if left_core != right_core:
        return (right_core > left_core) - (right_core < left_core)

    # Return candidate relative to current.
    return compare_prerelease(right[3], left[3])


def parse_yyyymmdd(value):
    if not re.fullmatch(r"\d{8}", value or ""):
        return None

    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def compare_yyyymmdd(current, candidate):
    left = parse_yyyymmdd(current)
    right = parse_yyyymmdd(candidate)

    if left is None or right is None:
        return None

    return (right > left) - (right < left)


def compare_integer(current, candidate):
    if not re.fullmatch(r"\d+", current or ""):
        return None

    if not re.fullmatch(r"\d+", candidate or ""):
        return None

    left = int(current)
    right = int(candidate)

    return (right > left) - (right < left)


def resolve_parser(registry, repository):
    for rule in registry.get("rules", []):
        if rule.get("repository") == repository:
            return rule.get("parser")

    return (registry.get("defaults") or {}).get("parser", "semver")


def result_payload(
    current,
    candidate,
    parser,
    result,
    method,
    reason,
    image_type,
):
    repository = (
        current["repository"]
        if current["repository"] == candidate["repository"]
        else None
    )

    return {
        "candidate": candidate["reference"],
        "candidate_digest": candidate["digest"],
        "candidate_tag": candidate["tag"],
        "current": current["reference"],
        "current_digest": current["digest"],
        "current_tag": current["tag"],
        "image_type": image_type,
        "method": method,
        "parser": parser,
        "repository": repository,
        "result": result,
        "reason": reason,
    }


def main():
    args = parse_args()

    registry_path = Path(args.registry)

    if not registry_path.is_file():
        raise SystemExit(
            f"ERROR: version scheme registry not found: {registry_path}"
        )

    with registry_path.open("r", encoding="utf-8") as handle:
        registry = yaml.safe_load(handle) or {}

    current = split_reference(args.current)
    candidate = split_reference(args.candidate)

    if args.image_type == "local-build":
        local_policy = registry.get("local_build") or {}

        payload = result_payload(
            current,
            candidate,
            local_policy.get("parser", "provenance"),
            local_policy.get(
                "result",
                "local-build-provenance-required",
            ),
            "local-build-provenance",
            "Local builds are compared through source provenance, not tags.",
            args.image_type,
        )

        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    if (
        current["digest"]
        and candidate["digest"]
        and current["digest"] == candidate["digest"]
    ):
        payload = result_payload(
            current,
            candidate,
            "digest",
            "same",
            "exact-digest",
            "Current and candidate resolve to the same immutable digest.",
            args.image_type,
        )

        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    if current["reference"] == candidate["reference"]:
        payload = result_payload(
            current,
            candidate,
            "exact-reference",
            "same",
            "exact-reference",
            "Current and candidate image references are identical.",
            args.image_type,
        )

        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    if current["repository"] != candidate["repository"]:
        payload = result_payload(
            current,
            candidate,
            None,
            "ordering-unknown-blocked",
            "repository-change",
            "Image repositories differ; ordering cannot be established safely.",
            args.image_type,
        )

        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    parser = resolve_parser(
        registry,
        current["repository"],
    )

    if current["tag"] == candidate["tag"]:
        payload = result_payload(
            current,
            candidate,
            parser,
            "ordering-unknown-blocked",
            "same-tag-different-identity",
            "Tag is unchanged but immutable identity differs or is incomplete.",
            args.image_type,
        )

        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    if parser in {"opaque", "channel"}:
        payload = result_payload(
            current,
            candidate,
            parser,
            "ordering-unknown-blocked",
            f"{parser}-tag",
            f"{parser} image tags are not safely orderable.",
            args.image_type,
        )

        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    if parser == "semver":
        comparison = compare_semver(
            current["tag"],
            candidate["tag"],
        )
    elif parser == "yyyymmdd":
        comparison = compare_yyyymmdd(
            current["tag"],
            candidate["tag"],
        )
    elif parser == "integer":
        comparison = compare_integer(
            current["tag"],
            candidate["tag"],
        )
    else:
        comparison = None

    if comparison is None:
        payload = result_payload(
            current,
            candidate,
            parser,
            "ordering-unknown-blocked",
            "parser-unable-to-order",
            "Configured parser could not safely order the image tags.",
            args.image_type,
        )

    elif comparison > 0:
        payload = result_payload(
            current,
            candidate,
            parser,
            "upgrade",
            f"{parser}-comparison",
            "Candidate version is newer than the current version.",
            args.image_type,
        )

    elif comparison < 0:
        payload = result_payload(
            current,
            candidate,
            parser,
            "downgrade-blocked",
            f"{parser}-comparison",
            "Candidate version is older than the current version.",
            args.image_type,
        )

    else:
        payload = result_payload(
            current,
            candidate,
            parser,
            "same",
            f"{parser}-comparison",
            "Current and candidate versions are equivalent.",
            args.image_type,
        )

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
