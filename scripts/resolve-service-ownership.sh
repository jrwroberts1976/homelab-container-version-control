#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")"
  pwd
)"

PROJECT_ROOT="$(
  cd "${SCRIPT_DIR}/.."
  pwd
)"

REGISTRY="${SERVICE_OWNERSHIP_REGISTRY:-${PROJECT_ROOT}/config/service-ownership.yml}"
CONTAINER="${1:-}"

if [[ -z "$CONTAINER" ]]; then
    echo "Usage: $0 <container>" >&2
    exit 2
fi

if [[ ! -r "$REGISTRY" ]]; then
    echo "ERROR: ownership registry is not readable: $REGISTRY" >&2
    exit 3
fi

command -v docker >/dev/null 2>&1 || {
    echo "ERROR: docker is required" >&2
    exit 3
}

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR: python3 is required" >&2
    exit 3
}

python3 -c 'import yaml' >/dev/null 2>&1 || {
    echo "ERROR: Python PyYAML is required" >&2
    exit 3
}

INSPECT_JSON="$(docker inspect "$CONTAINER" 2>/dev/null)" || {
    echo "ERROR: container not found or Docker inspect failed: $CONTAINER" >&2
    exit 4
}

DOCKER_INSPECT_JSON="$INSPECT_JSON" \
python3 - "$REGISTRY" <<'PY'
import json
import os
import sys
import yaml

registry_path = sys.argv[1]

with open(registry_path, "r", encoding="utf-8") as fh:
    registry = yaml.safe_load(fh)

try:
    inspected = json.loads(os.environ["DOCKER_INSPECT_JSON"])
except (KeyError, json.JSONDecodeError) as exc:
    raise SystemExit(f"ERROR: invalid docker inspect JSON: {exc}")

if len(inspected) != 1:
    raise SystemExit(
        f"ERROR: expected exactly one container, got {len(inspected)}"
    )

container = inspected[0]

labels = container.get("Config", {}).get("Labels") or {}

name = (container.get("Name") or "").lstrip("/")
project = labels.get("com.docker.compose.project", "")
service = labels.get("com.docker.compose.service", "")
working_dir = labels.get(
    "com.docker.compose.project.working_dir",
    "",
)
config_files = labels.get(
    "com.docker.compose.project.config_files",
    "",
)

if not project or not service:
    raise SystemExit(
        f"ERROR: {name or 'container'} has no Compose ownership labels"
    )

defaults = registry.get("defaults") or {}
overrides = registry.get("overrides") or []

matches = [
    entry
    for entry in overrides
    if entry.get("compose_project") == project
    and entry.get("compose_service") == service
]

if len(matches) > 1:
    raise SystemExit(
        f"ERROR: duplicate ownership overrides for {project}/{service}"
    )

if matches:
    rule = {**defaults, **matches[0]}

    runtime_compose = (
        rule.get("runtime_compose")
        or config_files
        or None
    )

    source_compose = rule.get("source_compose")

else:
    rule = dict(defaults)

    runtime_root = os.path.normpath(
        str(rule.get("runtime_root") or "")
    )
    normalized_working_dir = os.path.normpath(working_dir)

    if (
        not runtime_root
        or normalized_working_dir == runtime_root
        or not normalized_working_dir.startswith(
            runtime_root + os.sep
        )
    ):
        if normalized_working_dir != runtime_root:
            raise SystemExit(
                "ERROR: service is outside the default authority root "
                f"and has no override: {project}/{service} "
                f"({working_dir})"
            )

    source_files = []

    for runtime_file in filter(
        None,
        (item.strip() for item in config_files.split(",")),
    ):
        normalized_file = os.path.normpath(runtime_file)

        if normalized_file == runtime_root:
            raise SystemExit(
                f"ERROR: invalid Compose file path: {runtime_file}"
            )

        if not normalized_file.startswith(runtime_root + os.sep):
            raise SystemExit(
                "ERROR: Compose file is outside the default authority root: "
                f"{runtime_file}"
            )

        source_files.append(
            os.path.relpath(normalized_file, runtime_root)
        )

    if not source_files:
        raise SystemExit(
            f"ERROR: no authoritative Compose file for {project}/{service}"
        )

    runtime_compose = config_files
    source_compose = ",".join(source_files)

result = {
    "container": name,
    "compose_project": project,
    "compose_service": service,
    "authority": rule.get("authority"),
    "repository": rule.get("repository"),
    "source_compose": source_compose,
    "runtime_compose": runtime_compose,
    "working_dir": working_dir,
    "image_type": rule.get("image_type"),
    "exception": rule.get("exception"),
    "validation": rule.get("validation"),
    "deployment_allowed": bool(
        rule.get("deployment_allowed", False)
    ),
}

print(json.dumps(result, indent=2, sort_keys=True))
PY
