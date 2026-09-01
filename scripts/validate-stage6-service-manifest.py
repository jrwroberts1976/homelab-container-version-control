#!/usr/bin/env python3

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)

SUPPORTED_DOCKER_HOSTS = {
    "TestServer": "arm64",
    "ids-01": "amd64",
}


def fail(message: str) -> None:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot load {path}: {exc}")


def semver_key(version: str):
    match = SEMVER_RE.fullmatch(version)
    if not match:
        fail(f"invalid semver: {version}")

    release = (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )

    pre = match.group("pre")
    if pre is None:
        return release + ((1,),)

    parts = []
    for item in pre.split("."):
        if item.isdigit():
            parts.append((0, int(item)))
        else:
            parts.append((1, item))

    return release + ((0, tuple(parts)),)


def validate_datetime(value: str) -> None:
    require(isinstance(value, str) and value, "candidate.created missing")
    parsed = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt.datetime.fromisoformat(parsed)
    except ValueError:
        fail(f"candidate.created is not ISO-8601: {value}")


def validate_manifest(manifest: dict) -> None:
    require(manifest.get("schema_version") == 1, "schema_version must be 1")
    require(
        manifest.get("artifact") == "service-update-manifest",
        "artifact must be service-update-manifest",
    )
    require(manifest.get("mode") == "stage6-generic", "mode must be stage6-generic")

    service = manifest.get("service") or {}
    compose = service.get("compose") or {}
    authority = manifest.get("authority") or {}
    versions = manifest.get("versions") or {}
    rollback = versions.get("rollback") or {}
    candidate = versions.get("candidate") or {}
    runtime = manifest.get("runtime") or {}
    health = manifest.get("health") or {}
    protection = manifest.get("protection") or {}
    execution = manifest.get("execution") or {}

    require(service.get("image_type") == "registry-image", "Stage 6 v1 accepts registry-image only")
    require(service.get("risk_class") in {"low", "medium"}, "risk class must be low or medium")
    require(service.get("name") == service.get("container"), "v1 service/container identity must match")
    require(service.get("name") == compose.get("service"), "v1 service/Compose service identity must match")
    host = str(service.get("host", ""))
    require(
        host in SUPPORTED_DOCKER_HOSTS,
        "Stage 6 Docker host is not reviewed",
    )
    expected_architecture = SUPPORTED_DOCKER_HOSTS[host]

    for key in ("project_directory", "compose_file"):
        value = compose.get(key)
        require(isinstance(value, str) and value.startswith("/"), f"compose.{key} must be absolute")

    image_variable = compose.get("image_variable")
    require(
        isinstance(image_variable, str)
        and re.fullmatch(r"[A-Z][A-Z0-9_]*", image_variable) is not None,
        "compose.image_variable must be an uppercase environment variable name",
    )

    require(authority.get("repository") == "docker-env", "authority.repository must be docker-env")
    require(COMMIT_RE.fullmatch(str(authority.get("revision", ""))) is not None, "authority revision invalid")
    require(SHA_RE.fullmatch(str(authority.get("compose_sha256", ""))) is not None, "authority compose SHA invalid")

    authority_compose_path = authority.get("compose_path")

    if authority_compose_path is not None:
        require(
            isinstance(authority_compose_path, str)
            and authority_compose_path,
            "authority compose path must be a non-empty string",
        )

        authority_path = Path(authority_compose_path)

        require(
            not authority_path.is_absolute(),
            "authority compose path must be relative",
        )
        require(
            ".." not in authority_path.parts,
            "authority compose path traversal rejected",
        )

    if host == "ids-01":
        require(
            isinstance(authority_compose_path, str)
            and authority_compose_path,
            "ids-01 requires reviewed authority compose path",
        )
        require(
            authority_compose_path.startswith("hosts/ids-01/"),
            "ids-01 authority compose path must remain under hosts/ids-01",
        )
    elif authority_compose_path is not None:
        require(
            authority_compose_path.startswith("stacks/"),
            "TestServer authority compose path must remain under stacks",
        )

    require(versions.get("scheme") in {"semver", "yyyymmdd", "integer", "opaque", "channel", "provenance"}, "unknown version scheme")

    rollback_repo = rollback.get("image_repository")
    candidate_repo = candidate.get("image_repository")
    require(rollback_repo == candidate_repo and bool(rollback_repo), "candidate and rollback repositories must match")

    rollback_configured_image = rollback.get("configured_image")
    rollback_prefix = f"{rollback_repo}:"
    require(
        isinstance(rollback_configured_image, str)
        and rollback_configured_image.startswith(rollback_prefix)
        and len(rollback_configured_image) > len(rollback_prefix)
        and "@" not in rollback_configured_image
        and re.search(r"\s", rollback_configured_image) is None,
        "rollback configured_image must be an exact tagged image in rollback repository",
    )

    for label, item in (("rollback", rollback), ("candidate", candidate)):
        digest = item.get("index_digest")
        immutable_ref = item.get("immutable_ref")
        require(DIGEST_RE.fullmatch(str(digest or "")) is not None, f"{label} index digest invalid")
        require(
            immutable_ref == f"{item.get('image_repository')}@{digest}",
            f"{label} immutable_ref does not exactly match repository@index_digest",
        )
        platform = item.get("platform") or {}
        require(platform.get("os") == "linux", f"{label} OS must be linux")
        require(
            platform.get("architecture") == expected_architecture,
            f"{label} architecture must be {expected_architecture} for {host}",
        )

    require(
        DIGEST_RE.fullmatch(str(rollback.get("local_image_id") or "")) is not None,
        "rollback local image ID invalid",
    )
    require(
        candidate.get("platform_manifest_digest")
        and DIGEST_RE.fullmatch(candidate["platform_manifest_digest"]) is not None,
        "candidate platform manifest digest invalid",
    )
    require(
        candidate.get("config_digest")
        and DIGEST_RE.fullmatch(candidate["config_digest"]) is not None,
        "candidate config digest invalid",
    )

    candidate_local_image_id = candidate.get("local_image_id")

    if host == "ids-01":
        require(
            DIGEST_RE.fullmatch(str(candidate_local_image_id or "")) is not None,
            "ids-01 candidate local image ID required",
        )
    elif candidate_local_image_id is not None:
        require(
            DIGEST_RE.fullmatch(str(candidate_local_image_id)) is not None,
            "candidate local image ID invalid",
        )

    require(candidate.get("index_digest") != rollback.get("index_digest"), "candidate equals rollback digest")
    validate_datetime(candidate.get("created", ""))

    metadata_verification = candidate.get(
        "metadata_verification",
        "oci-labels",
    )
    require(
        metadata_verification in {"oci-labels", "digest-pinned"},
        "candidate metadata verification mode invalid",
    )

    if versions.get("scheme") == "semver":
        require(
            semver_key(str(candidate.get("version", ""))) > semver_key(str(rollback.get("version", ""))),
            "semver candidate is not newer than rollback",
        )

    networks = runtime.get("networks") or []
    require(networks and len(networks) == len(set(networks)), "runtime networks must be non-empty and unique")
    require(runtime.get("privileged") is False, "privileged containers are not eligible")

    devices_allowed = runtime.get("devices_allowed")
    require(
        isinstance(devices_allowed, bool),
        "runtime.devices_allowed must be boolean",
    )

    devices = runtime.get("devices") or []
    require(
        isinstance(devices, list),
        "runtime.devices must be an array",
    )

    if devices_allowed:
        require(
            host == "TestServer",
            "reviewed audio-device access is currently TestServer-only",
        )
        require(
            service.get("risk_class") == "medium",
            "audio-device eligibility requires medium risk class",
        )
        require(
            len(devices) == 1,
            "audio-device eligibility requires exactly one device mapping",
        )

        device = devices[0]

        require(
            isinstance(device, dict),
            "runtime device entry must be an object",
        )
        require(
            device.get("source") == "/dev/snd",
            "audio device source must be exactly /dev/snd",
        )
        require(
            device.get("destination") == "/dev/snd",
            "audio device destination must be exactly /dev/snd",
        )
        require(
            device.get("permissions") == "rwm",
            "audio device permissions must be exactly rwm",
        )
    else:
        require(
            not devices,
            "device mappings require devices_allowed=true",
        )

    docker_socket_allowed = runtime.get("docker_socket_allowed")

    require(
        isinstance(docker_socket_allowed, bool),
        "runtime.docker_socket_allowed must be boolean",
    )

    if devices_allowed:
        require(
            docker_socket_allowed is False,
            "audio-device workloads may not also expose the Docker socket",
        )

    mounts = runtime.get("mounts") or []
    socket_mounts = []
    docker_socket_named_mounts = []

    for mount in mounts:
        source = str(mount.get("source", ""))
        destination = str(mount.get("destination", ""))
        sha = mount.get("sha256")

        if "docker.sock" in source or "docker.sock" in destination:
            docker_socket_named_mounts.append(mount)

        if mount.get("type") == "bind":
            require(
                source.startswith("/"),
                "bind source must be absolute",
            )

            source_kind = mount.get("source_kind", "file")

            require(
                source_kind in {"file", "directory", "socket"},
                "bind source_kind must be file, directory or socket",
            )

            if source_kind == "file":
                require(
                    SHA_RE.fullmatch(str(sha or "")) is not None,
                    "file bind mount must carry a SHA-256 invariant",
                )

            elif source_kind == "directory":
                require(
                    sha is None,
                    "directory bind mount must use sha256 null",
                )

            else:
                require(
                    sha is None,
                    "socket bind mount must use sha256 null",
                )

                socket_mounts.append(mount)

        else:
            require(
                mount.get("source_kind") != "socket",
                "socket source_kind requires a bind mount",
            )

    if docker_socket_allowed:
        require(
            service.get("risk_class") == "medium",
            "Docker socket eligibility requires medium risk class",
        )

        require(
            len(socket_mounts) == 1,
            "Docker socket eligibility requires exactly one socket bind mount",
        )

        socket_mount = socket_mounts[0]

        require(
            socket_mount.get("source") == "/var/run/docker.sock",
            "Docker socket source must be exactly /var/run/docker.sock",
        )

        require(
            socket_mount.get("destination") == "/var/run/docker.sock",
            "Docker socket destination must be exactly /var/run/docker.sock",
        )

        require(
            socket_mount.get("rw") is False,
            "Docker socket mount must be read-only",
        )

        require(
            socket_mount.get("source_kind") == "socket",
            "Docker socket mount must use source_kind socket",
        )

        require(
            socket_mount.get("sha256") is None,
            "Docker socket mount must use sha256 null",
        )

        require(
            len(docker_socket_named_mounts) == 1,
            "only the exact reviewed Docker socket path is permitted",
        )

    else:
        require(
            not socket_mounts,
            "socket bind mounts require docker_socket_allowed=true",
        )

        require(
            not docker_socket_named_mounts,
            "Docker socket mount blocked",
        )

    compose_exec = runtime.get("compose_execution") or {}
    require(compose_exec.get("no_deps") is True, "Compose --no-deps required")
    require(compose_exec.get("no_build") is True, "Compose --no-build required")
    require(compose_exec.get("pull") == "never", "Compose --pull never required")
    require(compose_exec.get("force_recreate") is True, "Compose --force-recreate required")

    health_strategy = health.get("strategy")

    require(
        health_strategy in {"docker-health", "http", "container-http"},
        "unsupported health strategy",
    )
    require(
        isinstance(health.get("timeout_seconds"), int)
        and 1 <= health["timeout_seconds"] <= 900,
        "health timeout invalid",
    )

    if health_strategy == "docker-health":
        require(
            health.get("expected") == "healthy",
            "docker-health expected state must be healthy",
        )

    elif health_strategy == "http":
        health_url = str(health.get("url", ""))

        require(
            health_url.startswith(("http://", "https://")),
            "HTTP health URL invalid",
        )
        require(
            isinstance(health.get("expected_status"), int),
            "HTTP expected_status missing",
        )

        if host == "ids-01":
            require(
                health_url.startswith("http://127.0.0.1:")
                or health_url.startswith("http://localhost:"),
                "ids-01 HTTP health URL must be local",
            )

    else:
        require(
            host == "TestServer",
            "container-http is currently reviewed for TestServer only",
        )

        health_network = health.get("network")
        health_port = health.get("container_port")
        health_path = health.get("path")

        require(
            isinstance(health_network, str)
            and health_network
            and health_network in networks,
            "container-http network must be one reviewed runtime network",
        )
        require(
            isinstance(health_port, int)
            and 1 <= health_port <= 65535,
            "container-http port invalid",
        )
        require(
            isinstance(health_path, str)
            and health_path.startswith("/"),
            "container-http path invalid",
        )
        require(
            isinstance(health.get("expected_status"), int)
            and 100 <= health["expected_status"] <= 599,
            "container-http expected_status invalid",
        )

    protected = set(protection.get("containers") or [])

    if host == "TestServer":
        require(
            {"jenkins", "jenkins-docker"}.issubset(protected),
            "Jenkins and Jenkins-DinD must be protected",
        )
    else:
        require(
            {"grafana", "loki"}.issubset(protected),
            "ids-01 monitoring protection must include Grafana and Loki",
        )
    require(protection.get("all_other_containers_unchanged") is True, "all unrelated containers must remain unchanged")
    compare = set(protection.get("compare") or [])
    require({"container_id", "restart_count"}.issubset(compare), "protected comparison must include ID and restart count")

    required_execution = {
        "human_approval_required": True,
        "post_approval_reinspection_required": True,
        "one_shot_required": True,
        "candidate_acquisition": "separate-reviewed-step",
        "candidate_must_be_local_before_arm": True,
        "deployment_pull_allowed": False,
        "rollback_required": True,
        "rollback_only_for_consumed_pilot": True,
    }
    for key, expected in required_execution.items():
        require(execution.get(key) == expected, f"execution.{key} must be {expected!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--schema", type=Path)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    require(isinstance(manifest, dict), "manifest root must be an object")

    if args.schema is not None:
        schema = load_json(args.schema)
        require(isinstance(schema, dict), "schema root must be an object")
        try:
            import jsonschema  # type: ignore
        except ImportError:
            print("INFO: jsonschema package unavailable; running invariant validator only")
        else:
            jsonschema.Draft202012Validator.check_schema(schema)
            try:
                jsonschema.Draft202012Validator(schema).validate(manifest)
            except jsonschema.ValidationError as exc:
                fail(f"JSON Schema validation: {exc.message}")
            print("PASS: JSON Schema validation")

    validate_manifest(manifest)
    print("PASS: Stage 6 cross-field and security invariants")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
