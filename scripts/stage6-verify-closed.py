#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HEX40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
IMMUTABLE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]*\.json$")


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception as exc:
        fail(f"cannot read JSON {path}: {exc}")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_checked(cmd, *, capture=False):
    try:
        return subprocess.run(
            cmd,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except subprocess.CalledProcessError as exc:
        if capture and exc.stderr:
            print(exc.stderr.rstrip(), file=sys.stderr)
        fail(f"command failed: {cmd[0]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--known-hosts", required=True)
    parser.add_argument("--hostkey-fingerprint", required=True)
    parser.add_argument("--ssh-user", required=True)
    parser.add_argument("--ssh-key", required=True)
    parser.add_argument("--artifact-dir", default="artifacts")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if manifest_path.parent.as_posix() != "config/services":
        fail("manifest must be under config/services")
    if not SAFE_NAME.fullmatch(manifest_path.name):
        fail("manifest filename is unsafe")

    if args.ssh_user != "homelab-stage6-inspector":
        fail("VERIFY_CLOSED requires the inspector identity")

    required = [
        manifest_path,
        Path("config/estate-updater-catalog.json"),
        Path("config/service-update-manifest.schema.json"),
        Path("config/steady-state-manifest.schema.json"),
        Path("scripts/validate-stage6-service-manifest.py"),
        Path("scripts/validate-stage6-steady-state-manifest.py"),
        Path("ops/testserver/homelab-stage6-inspector-ssh"),
        Path("ops/testserver/homelab-stage6-inspector-sudoers"),
        Path("ops/testserver/homelab-stage6-steady-inspect"),
        Path(args.known_hosts),
        Path(args.ssh_key),
    ]
    for path in required:
        if not path.is_file():
            fail(f"required file missing: {path}")

    wrapper = Path("ops/testserver/homelab-stage6-inspector-ssh").read_text()
    sudoers = Path("ops/testserver/homelab-stage6-inspector-sudoers").read_text()
    marker = "/usr/local/libexec/homelab-stage6-steady-inspect"
    if marker not in wrapper or marker not in sudoers:
        fail("steady-state inspector is outside the reviewed inspector boundary")

    keyscan = run_checked(
        ["ssh-keygen", "-lf", args.known_hosts, "-E", "sha256"],
        capture=True,
    ).stdout
    fingerprints = {
        line.split()[1]
        for line in keyscan.splitlines()
        if len(line.split()) >= 2
    }
    if args.hostkey_fingerprint not in fingerprints:
        fail("known-hosts fingerprint does not match reviewed host key")

    run_checked([
        "python3",
        "scripts/validate-stage6-service-manifest.py",
        str(manifest_path),
        "--schema",
        "config/service-update-manifest.schema.json",
    ])

    selected = load_json(manifest_path)
    service = str(selected.get("service", {}).get("name", ""))
    host = str(selected.get("service", {}).get("host", ""))
    candidate = selected.get("versions", {}).get("candidate", {})
    version = str(candidate.get("version", ""))
    image = str(candidate.get("immutable_ref", ""))

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", service):
        fail("selected manifest service name is unsafe")
    if host != "TestServer":
        fail("VERIFY_CLOSED is currently reviewed only for TestServer")
    if not version:
        fail("selected manifest has no candidate version")
    if not IMMUTABLE.fullmatch(image):
        fail("selected manifest candidate is not an exact immutable image")

    catalogue = load_json("config/estate-updater-catalog.json")
    service_entry = catalogue.get("services", {}).get(service)
    if not isinstance(service_entry, dict):
        fail("service is absent from reviewed estate catalogue")
    host_entry = service_entry.get("hosts", {}).get("TestServer")
    if not isinstance(host_entry, dict):
        fail("service has no reviewed TestServer catalogue entry")

    if host_entry.get("manifest") != manifest_path.name:
        fail("selected STAGE6_MANIFEST does not match catalogue manifest")
    desired_version = str(service_entry.get("desired_version", ""))
    if desired_version != version or str(host_entry.get("current_version", "")) != version:
        fail("selected version is not the closed catalogue version")
    if str(host_entry.get("configured_image", "")) != image:
        fail("selected image does not match closed catalogue state")
    if host_entry.get("coverage") != "managed-tested" or host_entry.get("inspect_ready") is not True:
        fail("catalogue entry is not managed-tested and inspect-ready")

    declared = str(host_entry.get("steady_state_manifest", ""))
    candidates = [Path(f"config/steady-state/{service}-{version}.json")]
    if declared and SAFE_NAME.fullmatch(declared):
        candidates.append(Path("config/steady-state") / declared)
    steady_path = next((p for p in candidates if p.is_file()), None)
    if steady_path is None:
        fail("reviewed steady-state manifest not found")

    run_checked([
        "python3",
        "scripts/validate-stage6-steady-state-manifest.py",
        str(steady_path),
    ])

    steady = load_json(steady_path)
    svc = steady.get("service", {})
    desired = steady.get("desired", {})
    authority = steady.get("authority", {})

    if (
        svc.get("name") != service
        or svc.get("container") != service
        or svc.get("compose", {}).get("service") != service
        or svc.get("host") != "TestServer"
        or svc.get("image_type") != "registry-image"
    ):
        fail("steady-state service identity mismatch")

    if (
        str(desired.get("version", "")) != version
        or str(desired.get("configured_image", "")) != image
        or str(desired.get("immutable_ref", "")) != image
    ):
        fail("selected manifest and steady-state desired identity disagree")

    local_image_id = str(desired.get("local_image_id", ""))
    revision = str(authority.get("revision", ""))
    compose_sha = str(authority.get("compose_sha256", ""))
    expected_health = str(steady.get("health", {}).get("expected", ""))

    if not SHA256.fullmatch(local_image_id):
        fail("steady-state local image ID is invalid")
    if not HEX40.fullmatch(revision):
        fail("steady-state authority revision is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", compose_sha):
        fail("steady-state Compose SHA is invalid")

    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"stage6-{service}-verify-closed.json"
    summary_path = artifact_dir / f"stage6-{service}-verify-closed-summary.json"

    ssh = [
        "ssh",
        "-n",
        "-i", args.ssh_key,
        "-o", "IdentitiesOnly=yes",
        "-o", "BatchMode=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={args.known_hosts}",
        f"{args.ssh_user}@{args.host}",
        f"steady-inspect {service}",
    ]
    inspected = run_checked(ssh, capture=True).stdout
    artifact_path.write_text(inspected)

    try:
        artifact = json.loads(inspected)
    except Exception as exc:
        fail(f"steady-state inspector did not return valid JSON: {exc}")

    if (
        artifact.get("schema_version") != 1
        or artifact.get("artifact") != "service-steady-state-inspection"
        or artifact.get("mode") != "read-only"
        or artifact.get("service") != service
        or artifact.get("host") != "TestServer"
        or artifact.get("result") != "steady-state-verified"
    ):
        fail("unexpected steady-state inspection identity")

    if (
        artifact.get("manifest", {}).get("sha256") != sha256_file(steady_path)
        or artifact.get("authority", {}).get("revision") != revision
        or artifact.get("authority", {}).get("compose_sha256") != compose_sha
        or artifact.get("authority", {}).get("clean") is not True
    ):
        fail("reviewed steady-state authority proof failed")

    actual_desired = artifact.get("desired", {})
    if (
        actual_desired.get("version") != version
        or actual_desired.get("configured_image") != image
        or actual_desired.get("immutable_ref") != image
        or actual_desired.get("local_image_id") != local_image_id
    ):
        fail("desired immutable image proof failed")

    if (
        artifact.get("runtime", {}).get("running") is not True
        or artifact.get("mutation_allowed") is not False
        or artifact.get("deployment", {}).get("allowed") is not False
        or artifact.get("deployment", {}).get("performed") is not False
    ):
        fail("closed-state verification was not strictly non-mutating")

    if expected_health and str(artifact.get("health", {}).get("status", "")) != expected_health:
        fail("steady-state health proof failed")

    protected = {
        str(item.get("name", "")): item
        for item in artifact.get("protected_containers", [])
        if isinstance(item, dict)
    }
    for name in ("jenkins", "jenkins-docker"):
        if protected.get(name, {}).get("running") is not True:
            fail(f"protected control-plane evidence failed for {name}")

    summary = {
        "schema_version": 1,
        "artifact": "stage6-verify-closed-result",
        "service": service,
        "host": "TestServer",
        "desired_version": version,
        "configured_image": image,
        "authority_revision": revision,
        "compose_sha256": compose_sha,
        "mutation_performed": False,
        "deployment_performed": False,
        "result": "SUCCESS_VERIFIED_CLOSED",
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"PASS: VERIFY_CLOSED resolved {service} {version} from reviewed manifest and steady-state authority")
    print(f"SUCCESS_VERIFIED_CLOSED: {service} matches reviewed authority, desired state and runtime without mutation")


if __name__ == "__main__":
    main()
