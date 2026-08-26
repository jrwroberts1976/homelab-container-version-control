#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OWNERSHIP_RESOLVER = PROJECT_ROOT / "scripts" / "resolve-service-ownership.sh"
COMPARATOR = PROJECT_ROOT / "scripts" / "compare-image-version.py"

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def fail(message):
    raise SystemExit(f"ERROR: {message}")


def run(command, cwd=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(
            f"command failed ({result.returncode}): "
            f"{' '.join(command)}"
            + (f": {detail}" if detail else "")
        )

    return result.stdout


def run_discard_stdout(command, cwd=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        detail = result.stderr.strip()
        fail(
            f"command failed ({result.returncode}): "
            f"{' '.join(command)}"
            + (f": {detail}" if detail else "")
        )


def load_json(text, description):
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"invalid {description} JSON: {exc}")


def normalize_github_repository(remote):
    remote = remote.strip()

    prefixes = (
        "https://github.com/",
        "http://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    )

    repository = None

    for prefix in prefixes:
        if remote.startswith(prefix):
            repository = remote[len(prefix):]
            break

    if repository is None:
        fail("authority origin is not a recognised GitHub repository")

    repository = repository.removesuffix(".git").strip("/")

    if repository.count("/") != 1:
        fail("authority origin does not identify owner/repository")

    return repository


def git_repository(root):
    remote = run(
        ["git", "-C", str(root), "remote", "get-url", "origin"]
    ).strip()

    return normalize_github_repository(remote)


def git_clean(root):
    status = run(
        ["git", "-C", str(root), "status", "--porcelain"]
    )
    return not status.strip()


def git_revision(root):
    return run(
        ["git", "-C", str(root), "rev-parse", "HEAD"]
    ).strip()


def resolve_ownership(container):
    output = run(
        [str(OWNERSHIP_RESOLVER), container]
    )
    return load_json(output, "ownership resolver")


def compose_candidate(authority_root, ownership):
    source_compose = ownership.get("source_compose")

    if not source_compose:
        fail("ownership record has no source_compose")

    compose_files = [
        item.strip()
        for item in source_compose.split(",")
        if item.strip()
    ]

    if not compose_files:
        fail("ownership record has no usable Compose file")

    absolute_files = []

    root = authority_root.resolve()

    for relative in compose_files:
        candidate = (authority_root / relative).resolve()

        try:
            candidate.relative_to(root)
        except ValueError:
            fail(f"Compose source escapes authority root: {relative}")

        if not candidate.is_file():
            fail(f"authoritative Compose file not found: {candidate}")

        absolute_files.append(candidate)

    base_command = ["docker", "compose"]

    for compose_file in absolute_files:
        base_command.extend(["-f", str(compose_file)])

    # Validate the complete Compose model, but deliberately discard
    # rendered output so interpolated environment values are not captured
    # by the planner.
    run_discard_stdout(
        [*base_command, "config"],
        cwd=absolute_files[0].parent,
    )

    service_name = ownership.get("compose_service")

    if not service_name:
        fail("ownership record has no compose_service")

    image_output = run(
        [
            *base_command,
            "config",
            "--images",
            service_name,
        ],
        cwd=absolute_files[0].parent,
    )

    images = [
        line.strip()
        for line in image_output.splitlines()
        if line.strip()
    ]

    if len(images) != 1:
        fail(
            "expected exactly one resolved image for Compose service "
            f"{service_name}; got {len(images)}"
        )

    return {
        "image": images[0],
        "compose_files": [
            str(path.relative_to(root))
            for path in absolute_files
        ],
    }


def runtime_identity(container, candidate_image):
    inspected = load_json(
        run(["docker", "inspect", container]),
        "docker inspect",
    )

    if len(inspected) != 1:
        fail(
            f"expected one container from docker inspect, got "
            f"{len(inspected)}"
        )

    container_data = inspected[0]
    configured_image = (
        container_data.get("Config", {}).get("Image")
    )
    image_id = container_data.get("Image")

    if not configured_image or not image_id:
        fail("runtime container image identity is incomplete")

    images = load_json(
        run(["docker", "image", "inspect", image_id]),
        "docker image inspect",
    )

    if len(images) != 1:
        fail(
            f"expected one image from docker image inspect, got "
            f"{len(images)}"
        )

    image = images[0]

    architecture = image.get("Architecture")
    os_name = image.get("Os")
    repo_digests = image.get("RepoDigests") or []

    candidate_repository = split_reference(candidate_image)["repository"]

    matching = [
        item
        for item in repo_digests
        if split_reference(item)["repository"]
        == candidate_repository
    ]

    if len(matching) != 1:
        fail(
            "expected exactly one runtime RepoDigest for candidate "
            f"repository {candidate_repository}; got {len(matching)}"
        )

    digest = split_reference(matching[0])["digest"]

    if not digest or not DIGEST_RE.fullmatch(digest):
        fail("runtime RepoDigest is missing or invalid")

    return {
        "configured_image": configured_image,
        "image_id": image_id,
        "repo_digest": matching[0],
        "digest": digest,
        "architecture": architecture,
        "os": os_name,
        "created": image.get("Created"),
    }


def split_reference(reference):
    digest = None
    base = reference

    if "@" in reference:
        base, digest = reference.rsplit("@", 1)
        digest = digest.lower()

    last_slash = base.rfind("/")
    last_colon = base.rfind(":")

    if last_colon > last_slash:
        repository = base[:last_colon]
        tag = base[last_colon + 1 :]
    else:
        repository = base
        tag = None

    return {
        "repository": repository,
        "tag": tag,
        "digest": digest,
    }


def remote_identity(candidate_image, target_os, target_arch):
    human = run(
        [
            "docker",
            "buildx",
            "imagetools",
            "inspect",
            candidate_image,
        ]
    )

    top_digest = None

    for line in human.splitlines():
        if line.startswith("Digest:"):
            top_digest = line.split(":", 1)[1].strip()
            break

    if not top_digest or not DIGEST_RE.fullmatch(top_digest):
        fail("remote top-level digest is missing or invalid")

    raw = run(
        [
            "docker",
            "buildx",
            "imagetools",
            "inspect",
            "--raw",
            candidate_image,
        ]
    )

    manifest = load_json(raw, "remote OCI manifest")

    manifests = manifest.get("manifests")

    if not isinstance(manifests, list):
        fail(
            "remote candidate is not an OCI/Docker manifest index; "
            "single-manifest handling is not implemented"
        )

    matches = []

    for item in manifests:
        platform = item.get("platform") or {}

        if (
            platform.get("os") == target_os
            and platform.get("architecture") == target_arch
        ):
            matches.append(item)

    if len(matches) != 1:
        fail(
            f"expected exactly one {target_os}/{target_arch} "
            f"platform manifest; got {len(matches)}"
        )

    platform_digest = matches[0].get("digest")

    if (
        not platform_digest
        or not DIGEST_RE.fullmatch(platform_digest)
    ):
        fail("platform manifest digest is missing or invalid")

    return {
        "index_digest": top_digest,
        "media_type": manifest.get("mediaType"),
        "manifest_count": len(manifests),
        "platform_digest": platform_digest,
        "platform": {
            "os": target_os,
            "architecture": target_arch,
            **(
                {"variant": matches[0]["platform"]["variant"]}
                if matches[0].get("platform", {}).get("variant")
                else {}
            ),
        },
    }


def bind_digest(reference, digest):
    if not DIGEST_RE.fullmatch(digest):
        fail(f"invalid digest for comparison: {digest}")

    base = reference.rsplit("@", 1)[0]

    return f"{base}@{digest}"


def compare_images(
    current_reference,
    current_digest,
    candidate_reference,
    candidate_digest,
    image_type,
):
    current = bind_digest(
        current_reference,
        current_digest,
    )
    candidate = bind_digest(
        candidate_reference,
        candidate_digest,
    )

    output = run(
        [
            str(COMPARATOR),
            "--image-type",
            image_type,
            current,
            candidate,
        ]
    )

    return load_json(output, "image comparator")


def main():
    parser = argparse.ArgumentParser(
        description="Read-only Stage 4 candidate image planner."
    )
    parser.add_argument("container")
    parser.add_argument(
        "--authority-root",
        required=True,
        help="Explicit clean checkout of the authoritative Git repository.",
    )
    args = parser.parse_args()

    authority_root = Path(args.authority_root)

    if not authority_root.is_dir():
        fail(f"authority root not found: {authority_root}")

    ownership = resolve_ownership(args.container)

    if ownership.get("validation") != "read-only":
        fail("service ownership is not marked read-only")

    if ownership.get("deployment_allowed") is not False:
        fail("service ownership permits deployment")

    if ownership.get("authority") == "platform-exception":
        fail("platform-exception services are not automatically plannable")

    if not ownership.get("repository"):
        fail("service has no authoritative Git repository")

    image_type = ownership.get("image_type")

    if image_type not in {"registry-image", "local-build"}:
        fail(f"unsupported or missing image_type: {image_type}")

    if image_type == "local-build":
        fail(
            "local-build candidate planning requires provenance handling "
            "and is not implemented"
        )

    if not git_clean(authority_root):
        fail(f"authority checkout is dirty: {authority_root}")

    authority_repository = git_repository(authority_root)

    if authority_repository != ownership.get("repository"):
        fail(
            "authority checkout repository mismatch: "
            f"expected {ownership.get('repository')}, "
            f"got {authority_repository}"
        )

    revision = git_revision(authority_root)

    candidate = compose_candidate(
        authority_root,
        ownership,
    )

    runtime = runtime_identity(
        args.container,
        candidate["image"],
    )

    if not runtime["os"] or not runtime["architecture"]:
        fail("runtime image platform is incomplete")

    remote = remote_identity(
        candidate["image"],
        runtime["os"],
        runtime["architecture"],
    )

    comparison = compare_images(
        runtime["configured_image"],
        runtime["digest"],
        candidate["image"],
        remote["index_digest"],
        image_type,
    )

    result = {
        "schema_version": 1,
        "mode": "read-only",
        "container": args.container,
        "ownership": ownership,
        "authority": {
            "root": str(authority_root.resolve()),
            "repository": authority_repository,
            "revision": revision,
            "clean": True,
            "compose_files": candidate["compose_files"],
        },
        "runtime": runtime,
        "candidate": {
            "image": candidate["image"],
            **remote,
        },
        "comparison": comparison,
        "deployment": {
            "allowed": False,
            "performed": False,
        },
    }

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
