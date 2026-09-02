#!/usr/bin/env python3

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOGUE_PATH = PROJECT_ROOT / "config" / "estate-updater-catalog.json"
SCHEMA_PATH = PROJECT_ROOT / "config" / "service-update-manifest.schema.json"
VALIDATOR = PROJECT_ROOT / "scripts" / "validate-stage6-service-manifest.py"
SERVICES_DIR = PROJECT_ROOT / "config" / "services"
STEADY_DIR = PROJECT_ROOT / "config" / "steady-state"
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]*\.json$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception as exc:
        fail(f"cannot read JSON {path}: {exc}")


def run(command, *, capture=True):
    proc = subprocess.run(
        [str(x) for x in command],
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if proc.returncode != 0:
        detail = ""
        if capture:
            detail = (proc.stderr or proc.stdout or "").strip()
        fail(
            f"command failed ({proc.returncode}): {command[0]}"
            + (f": {detail}" if detail else "")
        )
    return proc.stdout if capture else ""


def resolve_request(manifest_name, catalogue):
    if not SAFE_NAME.fullmatch(manifest_name):
        fail("requested manifest filename is unsafe")

    matches = []
    for service in catalogue.get("services", {}):
        prefix = f"{service}-"
        if manifest_name.startswith(prefix) and manifest_name.endswith(".json"):
            version = manifest_name[len(prefix):-5]
            if version:
                matches.append((service, version))

    if not matches:
        fail("requested manifest does not map to a catalogue service")

    service, version = max(matches, key=lambda item: len(item[0]))
    return service, version


def steady_state_path(service, current_version, host_entry):
    exact = STEADY_DIR / f"{service}-{current_version}.json"
    if exact.is_file():
        return exact

    declared = str(host_entry.get("steady_state_manifest", ""))
    if declared and SAFE_NAME.fullmatch(declared):
        candidate = STEADY_DIR / declared
        if candidate.is_file():
            return candidate

    fail("reviewed current steady-state manifest not found")


def tag_candidates(repository, version, template):
    candidates = []

    rollback = template.get("versions", {}).get("rollback", {})
    old_version = str(rollback.get("version", ""))
    configured = str(rollback.get("configured_image", ""))
    prefix = f"{repository}:"

    if configured.startswith(prefix) and "@" not in configured:
        old_tag = configured[len(prefix):]
        if old_tag == old_version:
            candidates.append(f"{repository}:{version}")
        elif old_tag == f"v{old_version}":
            candidates.append(f"{repository}:v{version}")

    for ref in (f"{repository}:v{version}", f"{repository}:{version}"):
        if ref not in candidates:
            candidates.append(ref)

    return candidates


def inspect_verbose(reference):
    proc = subprocess.run(
        ["docker", "manifest", "inspect", "--verbose", reference],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def select_reference(repository, version, template):
    successes = []
    for reference in tag_candidates(repository, version, template):
        data = inspect_verbose(reference)
        if data is not None:
            successes.append((reference, data))

    if not successes:
        fail("no reviewed candidate tag convention resolved upstream")

    if len(successes) > 1:
        refs = ", ".join(item[0] for item in successes)
        fail(f"candidate tag convention is ambiguous upstream: {refs}")

    return successes[0]


def platform_manifest(verbose, os_name, architecture):
    items = verbose if isinstance(verbose, list) else [verbose]
    matches = []

    for item in items:
        platform = item.get("Descriptor", {}).get("platform", {})
        if (
            platform.get("os") == os_name
            and platform.get("architecture") == architecture
        ):
            matches.append(item)

    if len(matches) != 1:
        fail(
            f"expected exactly one {os_name}/{architecture} upstream manifest; "
            f"got {len(matches)}"
        )

    descriptor_digest = str(matches[0].get("Descriptor", {}).get("digest", ""))
    config_digest = str(
        matches[0].get("OCIManifest", {}).get("config", {}).get("digest", "")
    )

    if not DIGEST.fullmatch(descriptor_digest):
        fail("candidate platform manifest digest is invalid")
    if not DIGEST.fullmatch(config_digest):
        fail("candidate config digest is invalid")

    return descriptor_digest, config_digest


def normalize_repository(value):
    value = value.removeprefix("docker.io/")
    value = value.removeprefix("index.docker.io/")
    return value


def pulled_identity(reference, repository, os_name, architecture):
    run(
        ["docker", "pull", "--platform", f"{os_name}/{architecture}", reference],
        capture=False,
    )

    raw = run(["docker", "image", "inspect", reference])
    try:
        images = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"docker image inspect returned invalid JSON: {exc}")

    if len(images) != 1:
        fail("docker image inspect did not return exactly one candidate image")

    image = images[0]
    if image.get("Os") != os_name or image.get("Architecture") != architecture:
        fail("pulled candidate platform does not match reviewed host platform")

    repo_digests = image.get("RepoDigests") or []
    matches = []
    for item in repo_digests:
        if "@" not in item:
            continue
        repo, digest = item.rsplit("@", 1)
        if normalize_repository(repo) == normalize_repository(repository):
            matches.append(digest)

    matches = sorted(set(matches))
    if len(matches) != 1 or not DIGEST.fullmatch(matches[0]):
        fail("candidate index digest could not be resolved uniquely after pull")

    labels = image.get("Config", {}).get("Labels") or {}
    revision = str(labels.get("org.opencontainers.image.revision") or "")
    created = str(image.get("Created") or "")

    if not revision:
        fail("candidate OCI revision label is unavailable")
    if not created:
        fail("candidate created timestamp is unavailable")

    return {
        "index_digest": matches[0],
        "revision": revision,
        "created": created,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a missing Stage 6 service manifest as reviewed evidence. "
            "The candidate is pulled only into the local Jenkins Docker cache; "
            "no deployment is performed."
        )
    )
    parser.add_argument("--manifest-name", required=True)
    parser.add_argument("--host", default="TestServer")
    parser.add_argument("--output-dir", default="artifacts")
    args = parser.parse_args()

    requested_path = SERVICES_DIR / args.manifest_name
    if requested_path.exists():
        fail("requested manifest already exists; preparation is only for missing manifests")

    catalogue = load_json(CATALOGUE_PATH)
    service, version = resolve_request(args.manifest_name, catalogue)

    host_meta = catalogue.get("hosts", {}).get(args.host)
    if not isinstance(host_meta, dict) or host_meta.get("backend") != "docker-compose-stage6":
        fail("requested host is not an available Stage 6 Docker backend")

    platform_value = str(host_meta.get("platform", ""))
    if "/" not in platform_value:
        fail("reviewed host platform is unavailable")
    os_name, architecture = platform_value.split("/", 1)

    service_entry = catalogue.get("services", {}).get(service)
    if not isinstance(service_entry, dict):
        fail("service is absent from the estate catalogue")

    host_entry = service_entry.get("hosts", {}).get(args.host)
    if not isinstance(host_entry, dict):
        fail("service has no reviewed entry on requested host")
    if host_entry.get("coverage") != "managed-tested" or host_entry.get("inspect_ready") is not True:
        fail("service is not managed-tested and inspect-ready")

    current_version = str(host_entry.get("current_version", ""))
    current_manifest_name = str(host_entry.get("manifest", ""))
    if not current_version or not SAFE_NAME.fullmatch(current_manifest_name):
        fail("catalogue current manifest/version authority is incomplete")

    current_manifest_path = SERVICES_DIR / current_manifest_name
    if not current_manifest_path.is_file():
        fail("catalogue current Stage 6 manifest is missing")

    template = load_json(current_manifest_path)
    if template.get("service", {}).get("name") != service:
        fail("current manifest service identity mismatch")
    if template.get("service", {}).get("host") != args.host:
        fail("current manifest host identity mismatch")

    steady_path = steady_state_path(service, current_version, host_entry)
    steady = load_json(steady_path)

    if steady.get("service", {}).get("name") != service:
        fail("steady-state service identity mismatch")
    if steady.get("service", {}).get("host") != args.host:
        fail("steady-state host identity mismatch")

    desired = steady.get("desired", {})
    authority = steady.get("authority", {})

    if str(desired.get("version", "")) != current_version:
        fail("steady-state current version disagrees with catalogue")

    repository = str(desired.get("image_repository", ""))
    rollback_ref = str(desired.get("immutable_ref", ""))
    rollback_digest = str(desired.get("index_digest", ""))
    rollback_local_id = str(desired.get("local_image_id", ""))
    rollback_configured = str(desired.get("configured_image", ""))
    rollback_platform = desired.get("platform", {})

    if not repository:
        fail("steady-state image repository is unavailable")
    if rollback_ref != f"{repository}@{rollback_digest}":
        fail("steady-state rollback immutable identity is inconsistent")
    if not DIGEST.fullmatch(rollback_digest) or not DIGEST.fullmatch(rollback_local_id):
        fail("steady-state rollback digest/local image identity is invalid")
    if rollback_platform != {"os": os_name, "architecture": architecture}:
        fail("steady-state rollback platform disagrees with host platform")

    candidate_reference, verbose = select_reference(repository, version, template)
    platform_digest, config_digest = platform_manifest(
        verbose, os_name, architecture
    )
    pulled = pulled_identity(
        candidate_reference, repository, os_name, architecture
    )

    candidate_digest = pulled["index_digest"]
    if candidate_digest == rollback_digest:
        fail("requested candidate resolves to the current rollback digest")

    manifest = {
        "schema_version": 1,
        "artifact": "service-update-manifest",
        "mode": "stage6-generic",
        "service": copy.deepcopy(template["service"]),
        "authority": copy.deepcopy(authority),
        "versions": {
            "scheme": template["versions"]["scheme"],
            "rollback": {
                "version": current_version,
                "image_repository": repository,
                "configured_image": rollback_configured,
                "immutable_ref": rollback_ref,
                "index_digest": rollback_digest,
                "platform_manifest_digest": None,
                "local_image_id": rollback_local_id,
                "platform": {
                    "os": os_name,
                    "architecture": architecture,
                },
            },
            "candidate": {
                "version": version,
                "image_repository": repository,
                "immutable_ref": f"{repository}@{candidate_digest}",
                "index_digest": candidate_digest,
                "platform_manifest_digest": platform_digest,
                "config_digest": config_digest,
                "created": pulled["created"],
                "revision": pulled["revision"],
                "metadata_verification": "digest-pinned",
                "platform": {
                    "os": os_name,
                    "architecture": architecture,
                },
            },
        },
        "runtime": copy.deepcopy(template["runtime"]),
        "health": copy.deepcopy(template["health"]),
        "protection": copy.deepcopy(template["protection"]),
        "execution": copy.deepcopy(template["execution"]),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_path = output_dir / args.manifest_name
    output_path.write_text(json.dumps(manifest, indent=2) + "\n")

    run([
        sys.executable,
        str(VALIDATOR),
        str(output_path),
        "--schema",
        str(SCHEMA_PATH),
    ], capture=False)

    print(
        f"PASS: prepared Stage 6 manifest {args.manifest_name} "
        f"for {service} {version}"
    )
    print(f"candidate_source={candidate_reference}")
    print(f"candidate_index_digest={candidate_digest}")
    print(f"candidate_platform_digest={platform_digest}")
    print(f"candidate_config_digest={config_digest}")
    print(f"artifact={output_path}")
    print("MANIFEST_PREPARED_REVIEW_REQUIRED")


if __name__ == "__main__":
    main()
