#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
IMAGE_VARIABLE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
LIVE_ROOT = "/home/james/docker/"
DOCKER_SOCKET = "/var/run/docker.sock"
SUPPORTED_DOCKER_HOSTS = {"TestServer", "ids-01"}


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


def validate_manifest(manifest: dict) -> None:
    require(manifest.get("schema_version") == 1, "schema_version must be 1")
    require(
        manifest.get("artifact") == "service-steady-state-manifest",
        "artifact must be service-steady-state-manifest",
    )
    require(manifest.get("mode") == "stage6-steady-state", "invalid mode")

    authority = manifest.get("authority") or {}
    require(authority.get("repository") == "docker-env", "unsupported authority repository")
    require(bool(COMMIT_RE.fullmatch(str(authority.get("revision", "")))), "authority revision must be exact commit")
    require(bool(SHA_RE.fullmatch(str(authority.get("compose_sha256", "")))), "authority compose SHA-256 invalid")

    authority_compose_path = authority.get("compose_path")
    if authority_compose_path is not None:
        require(
            isinstance(authority_compose_path, str) and authority_compose_path,
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

    service = manifest.get("service") or {}
    service_name = str(service.get("name", ""))
    require(bool(SERVICE_RE.fullmatch(service_name)), "service name invalid")
    host = str(service.get("host", ""))
    require(
        host in SUPPORTED_DOCKER_HOSTS,
        "steady-state Docker host is not reviewed",
    )

    if host == "ids-01":
        require(
            isinstance(authority_compose_path, str) and authority_compose_path,
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

    require(service.get("image_type") == "registry-image", "steady-state backend supports registry-image only")
    require(service.get("risk_class") in {"low", "medium"}, "risk class must be low or medium")
    require(isinstance(service.get("container"), str) and service["container"], "container missing")

    compose = service.get("compose") or {}
    project_directory = str(compose.get("project_directory", ""))
    compose_file = str(compose.get("compose_file", ""))
    require(project_directory.startswith(LIVE_ROOT), "project directory outside fixed live root")
    require(compose_file.startswith(project_directory.rstrip("/") + "/"), "Compose file outside project directory")
    require(isinstance(compose.get("project"), str) and compose["project"], "Compose project missing")
    require(isinstance(compose.get("service"), str) and compose["service"], "Compose service missing")
    require(bool(IMAGE_VARIABLE_RE.fullmatch(str(compose.get("image_variable", "")))), "image variable invalid")

    desired = manifest.get("desired") or {}
    repository = str(desired.get("image_repository", ""))
    index_digest = str(desired.get("index_digest", ""))
    immutable_ref = str(desired.get("immutable_ref", ""))
    configured_image = str(desired.get("configured_image", ""))
    local_image_id = str(desired.get("local_image_id", ""))

    require(repository and "@" not in repository, "desired image repository invalid")
    require(bool(DIGEST_RE.fullmatch(index_digest)), "desired index digest invalid")
    require(immutable_ref == f"{repository}@{index_digest}", "immutable ref must equal repository@index_digest")
    require(configured_image == immutable_ref, "steady-state configured image must be exact immutable desired ref")
    require(bool(DIGEST_RE.fullmatch(local_image_id)), "desired local image ID invalid")
    require(isinstance(desired.get("version"), str) and desired["version"], "desired version missing")
    require(desired.get("metadata_verification") in {"digest-pinned", "oci-labels"}, "metadata verification mode invalid")

    platform = desired.get("platform") or {}
    require(platform.get("os") == "linux", "desired OS must be linux")
    require(platform.get("architecture") in {"arm64", "amd64"}, "desired architecture unsupported")

    runtime = manifest.get("runtime") or {}
    require(runtime.get("devices_allowed") is False, "initial steady-state backend forbids devices")
    require(isinstance(runtime.get("networks"), list), "runtime networks must be an array")
    require(isinstance(runtime.get("published_ports"), list), "runtime published_ports must be an array")
    require(isinstance(runtime.get("mounts"), list), "runtime mounts must be an array")
    require(isinstance(runtime.get("privileged"), bool), "runtime privileged must be boolean")
    require(isinstance(runtime.get("readonly_rootfs"), bool), "runtime readonly_rootfs must be boolean")
    require(isinstance(runtime.get("docker_socket_allowed"), bool), "docker_socket_allowed must be boolean")
    require(isinstance(runtime.get("restart_policy"), str) and runtime["restart_policy"], "restart policy missing")
    require(isinstance(runtime.get("user"), str), "runtime user must be string")

    socket_mounts = []
    socket_mentions = []
    for mount in runtime["mounts"]:
        require(mount.get("type") == "bind", "initial steady-state backend supports bind mounts only")
        source = str(mount.get("source", ""))
        destination = str(mount.get("destination", ""))
        source_kind = mount.get("source_kind")
        sha256 = mount.get("sha256")
        require(source and destination, "mount source/destination missing")
        require(isinstance(mount.get("rw"), bool), "mount rw must be boolean")
        require(source_kind in {"file", "directory", "socket"}, "mount source_kind invalid")

        if source_kind == "file":
            require(isinstance(sha256, str) and bool(SHA_RE.fullmatch(sha256)), f"file mount SHA-256 invalid: {source}")
        else:
            require(sha256 is None, f"{source_kind} mount must not carry SHA-256: {source}")

        if "docker.sock" in source or "docker.sock" in destination:
            socket_mentions.append(mount)
        if source == DOCKER_SOCKET and destination == DOCKER_SOCKET:
            socket_mounts.append(mount)

    content_checks = runtime.get("content_checks", [])
    require(
        isinstance(content_checks, list),
        "runtime content_checks must be an array",
    )

    directory_mount_sources = {
        str(mount.get("source", ""))
        for mount in runtime["mounts"]
        if mount.get("source_kind") == "directory"
    }

    seen_content_checks = set()

    for check in content_checks:
        require(
            isinstance(check, dict),
            "content check must be an object",
        )

        mount_source = str(check.get("mount_source", ""))
        relative = str(check.get("relative_path", ""))
        sha256 = str(check.get("sha256", ""))

        require(
            mount_source in directory_mount_sources,
            "content check mount_source must be an exact declared "
            "directory mount source",
        )

        mount_path = Path(mount_source)

        require(
            mount_path.is_absolute(),
            "content check mount_source must be absolute",
        )

        require(
            relative,
            "content check relative_path missing",
        )

        relative_path = Path(relative)

        require(
            not relative_path.is_absolute(),
            "content check relative_path must be relative",
        )

        require(
            ".." not in relative_path.parts,
            "content check path traversal rejected",
        )

        require(
            "." not in relative_path.parts,
            "content check relative_path must be normalized",
        )

        require(
            relative_path.as_posix() == relative,
            "content check relative_path must be normalized",
        )

        require(
            bool(SHA_RE.fullmatch(sha256)),
            "content check SHA-256 invalid",
        )

        identity = (mount_source, relative)

        require(
            identity not in seen_content_checks,
            "duplicate content check",
        )

        seen_content_checks.add(identity)

        content_path = mount_path / relative_path

        for other_source in directory_mount_sources:
            if other_source == mount_source:
                continue

            other_path = Path(other_source)

            try:
                other_path.relative_to(mount_path)
            except ValueError:
                continue

            try:
                content_path.relative_to(other_path)
            except ValueError:
                continue

            fail(
                "content check crosses a more-specific "
                "directory mount boundary"
            )

    if runtime["docker_socket_allowed"]:
        require(service.get("risk_class") == "medium", "Docker socket requires medium risk class")
        require(len(socket_mentions) == 1 and len(socket_mounts) == 1, "exactly one Docker socket mount required")
        socket = socket_mounts[0]
        require(socket.get("rw") is False, "Docker socket must be read-only")
        require(socket.get("source_kind") == "socket", "Docker socket source_kind must be socket")
        require(socket.get("sha256") is None, "Docker socket must not carry SHA-256")
    else:
        require(not socket_mentions, "Docker socket mount present while policy disabled")

    health = manifest.get("health") or {}
    strategy = health.get("strategy")
    require(
        strategy in {"docker-health", "http", "container-http"},
        "health strategy unsupported",
    )
    require(
        isinstance(health.get("expected"), str) and health["expected"],
        "health expected value missing",
    )

    if strategy == "http":
        url = str(health.get("url") or "")
        local_http = (
            url.startswith("http://127.0.0.1:")
            or url.startswith("http://localhost:")
        )

        if host == "TestServer":
            allowed_http = (
                local_http
                or url.startswith("http://192.168.2.220:")
            )
        else:
            allowed_http = local_http

        require(
            allowed_http,
            "HTTP health URL must be an approved local endpoint",
        )

        require(
            health.get("network") is None
            and health.get("container_port") is None
            and health.get("path") is None,
            "fixed HTTP health must not define container endpoint fields",
        )

    elif strategy == "container-http":
        network = health.get("network")
        port = health.get("container_port")
        path = health.get("path")

        require(
            health.get("url") is None,
            "container HTTP health must not define a fixed URL",
        )

        require(
            isinstance(network, str) and bool(network),
            "container HTTP health network missing",
        )

        require(
            network in runtime["networks"],
            "container HTTP health network is not a reviewed runtime network",
        )

        require(
            isinstance(port, int)
            and not isinstance(port, bool)
            and 1 <= port <= 65535,
            "container HTTP health port invalid",
        )

        require(
            isinstance(path, str)
            and path.startswith("/")
            and "\r" not in path
            and "\n" not in path
            and " " not in path
            and "\t" not in path,
            "container HTTP health path invalid",
        )

    protection = manifest.get("protection") or {}
    protected = protection.get("containers", [])
    require(isinstance(protected, list), "protection containers must be an array")
    require(len(protected) == len(set(protected)), "duplicate protected container")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Stage 6 steady-state manifest")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    try:
        manifest = load_json(args.manifest)
        require(isinstance(manifest, dict), "manifest root must be an object")
        validate_manifest(manifest)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"PASS: valid Stage 6 steady-state manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
