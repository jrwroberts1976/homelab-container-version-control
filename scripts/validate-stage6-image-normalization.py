#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

SUPPORTED_HOSTS = {
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
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot load {path}: {exc}")


def validate(manifest: dict) -> None:
    require(manifest.get("schema_version") == 1, "schema_version must be 1")
    require(
        manifest.get("artifact")
        == "service-image-normalization-manifest",
        "artifact must be service-image-normalization-manifest",
    )
    require(
        manifest.get("mode") == "stage6-image-ref-normalization",
        "mode must be stage6-image-ref-normalization",
    )

    service = manifest.get("service") or {}
    compose = service.get("compose") or {}
    authority = manifest.get("authority") or {}
    image = manifest.get("image") or {}
    source = image.get("source") or {}
    target = image.get("target") or {}
    rollback = image.get("rollback") or {}
    runtime = manifest.get("runtime") or {}
    health = manifest.get("health") or {}
    protection = manifest.get("protection") or {}
    execution = manifest.get("execution") or {}

    name = service.get("name")
    host = service.get("host")

    require(name == service.get("container"), "service/container identity must match")
    require(name == compose.get("service"), "service/Compose identity must match")
    require(service.get("image_type") == "registry-image", "registry-image required")
    require(service.get("risk_class") in {"low", "medium"}, "invalid risk class")
    require(host in SUPPORTED_HOSTS, "host is not reviewed")

    expected_arch = SUPPORTED_HOSTS[host]

    require(
        isinstance(compose.get("project_directory"), str)
        and compose["project_directory"].startswith("/"),
        "Compose project directory must be absolute",
    )
    require(
        isinstance(compose.get("compose_file"), str)
        and compose["compose_file"].startswith("/"),
        "Compose file must be absolute",
    )
    require(
        re.fullmatch(r"[A-Z][A-Z0-9_]*", str(compose.get("image_variable", "")))
        is not None,
        "invalid Compose image variable",
    )

    require(authority.get("repository") == "docker-env", "authority repository invalid")
    require(
        COMMIT_RE.fullmatch(str(authority.get("revision", ""))) is not None,
        "authority revision invalid",
    )
    require(
        SHA_RE.fullmatch(str(authority.get("compose_sha256", ""))) is not None,
        "authority Compose SHA invalid",
    )

    compose_path = authority.get("compose_path")

    if host == "ids-01":
        require(
            isinstance(compose_path, str)
            and compose_path.startswith("hosts/ids-01/")
            and ".." not in Path(compose_path).parts,
            "ids-01 requires safe hosts/ids-01 authority path",
        )
    elif compose_path is not None:
        require(
            isinstance(compose_path, str)
            and compose_path.startswith("stacks/")
            and ".." not in Path(compose_path).parts,
            "TestServer authority path invalid",
        )

    repository = image.get("repository")
    version = image.get("version")

    require(isinstance(repository, str) and repository, "image repository missing")
    require(isinstance(version, str) and version, "image version missing")
    require(image.get("same_content_required") is True, "same content must be required")

    source_ref = source.get("configured_image")
    rollback_ref = rollback.get("configured_image")
    target_ref = target.get("configured_image")
    target_digest = target.get("index_digest")

    prefix = f"{repository}:"

    require(
        isinstance(source_ref, str)
        and source_ref.startswith(prefix)
        and "@" not in source_ref
        and not re.search(r"\s", source_ref),
        "source must be an exact tagged image in reviewed repository",
    )

    require(
        rollback_ref == source_ref,
        "rollback must restore exact tagged source configuration",
    )

    require(
        DIGEST_RE.fullmatch(str(target_digest or "")) is not None,
        "target index digest invalid",
    )

    require(
        target_ref == f"{repository}@{target_digest}",
        "target immutable reference must exactly match repository@index_digest",
    )

    source_id = source.get("local_image_id")
    target_id = target.get("local_image_id")
    rollback_id = rollback.get("local_image_id")

    for label, value in (
        ("source", source_id),
        ("target", target_id),
        ("rollback", rollback_id),
    ):
        require(
            DIGEST_RE.fullmatch(str(value or "")) is not None,
            f"{label} local image ID invalid",
        )

    require(
        source_id == target_id == rollback_id,
        "source, target and rollback must prove identical local image content",
    )

    platform = image.get("platform") or {}

    require(platform.get("os") == "linux", "platform OS must be linux")
    require(
        platform.get("architecture") == expected_arch,
        f"platform architecture must be {expected_arch} for {host}",
    )

    networks = runtime.get("networks") or []

    require(networks, "runtime networks must be non-empty")
    require(len(networks) == len(set(networks)), "runtime networks must be unique")
    require(runtime.get("privileged") is False, "privileged runtime rejected")
    require(runtime.get("devices_allowed") is False, "device access rejected")
    require(runtime.get("docker_socket_allowed") is False, "Docker socket rejected")

    for mount in runtime.get("mounts") or []:
        if mount.get("type") == "bind":
            source_path = str(mount.get("source", ""))
            source_kind = mount.get("source_kind", "file")

            require(source_path.startswith("/"), "bind source must be absolute")
            require(
                source_kind in {"file", "directory"},
                "normalization bind source_kind invalid",
            )

            if source_kind == "file":
                require(
                    SHA_RE.fullmatch(str(mount.get("sha256") or "")) is not None,
                    "file bind requires SHA-256 invariant",
                )
            else:
                require(
                    mount.get("sha256") is None,
                    "directory bind must use sha256 null",
                )

    compose_exec = runtime.get("compose_execution") or {}

    require(compose_exec.get("no_deps") is True, "Compose --no-deps required")
    require(compose_exec.get("no_build") is True, "Compose --no-build required")
    require(compose_exec.get("pull") == "never", "Compose --pull never required")
    require(
        compose_exec.get("force_recreate") is True,
        "Compose --force-recreate required",
    )

    strategy = health.get("strategy")

    require(strategy in {"http", "container-http"}, "unsupported health strategy")
    require(
        isinstance(health.get("timeout_seconds"), int)
        and 1 <= health["timeout_seconds"] <= 900,
        "health timeout invalid",
    )
    require(
        isinstance(health.get("expected_status"), int)
        and 100 <= health["expected_status"] <= 599,
        "health expected status invalid",
    )

    if strategy == "http":
        require(
            str(health.get("url", "")).startswith(("http://", "https://")),
            "HTTP health URL invalid",
        )
    else:
        network = health.get("network")
        require(
            network in networks,
            "container-http health network must be a reviewed runtime network",
        )
        require(
            isinstance(health.get("container_port"), int)
            and 1 <= health["container_port"] <= 65535,
            "container-http port invalid",
        )
        require(
            isinstance(health.get("path"), str)
            and health["path"].startswith("/"),
            "container-http path invalid",
        )

    protected = set(protection.get("containers") or [])

    if host == "TestServer":
        require(
            {"jenkins", "jenkins-docker"}.issubset(protected),
            "TestServer must protect Jenkins and Jenkins-DinD",
        )
    else:
        require(
            {"grafana", "loki"}.issubset(protected),
            "ids-01 must protect Grafana and Loki",
        )

    require(
        protection.get("all_other_containers_unchanged") is True,
        "all unrelated containers must remain unchanged",
    )

    compare = set(protection.get("compare") or [])

    require(
        {"container_id", "restart_count"}.issubset(compare),
        "protected comparison must include container ID and restart count",
    )

    required_execution = {
        "human_approval_required": True,
        "post_approval_reinspection_required": True,
        "one_shot_required": True,
        "target_must_be_local_before_arm": True,
        "deployment_pull_allowed": False,
        "rollback_required": True,
        "rollback_ref_type": "tagged-source-configuration",
        "normalization_kind": "tag-to-immutable-same-content",
    }

    for key, expected in required_execution.items():
        require(
            execution.get(key) == expected,
            f"execution.{key} must be {expected!r}",
        )


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
            print(
                "INFO: jsonschema unavailable; "
                "running invariant validator only"
            )
        else:
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.Draft202012Validator(schema).validate(manifest)

    validate(manifest)

    print(
        "PASS: valid Stage 6 image-reference normalization manifest: "
        f"{args.manifest}"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(2)
