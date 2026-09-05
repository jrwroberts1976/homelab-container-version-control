#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path


SAFE_MANIFEST = re.compile(
    r"^[a-z0-9][a-z0-9.-]*\.json$"
)

SAFE_SERVICE = re.compile(
    r"^[a-z0-9][a-z0-9-]*$"
)


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


if len(sys.argv) != 2:
    fail(
        "usage: stage6-reviewed-manifest-selector.py "
        "UPDATE|VERIFY_CLOSED"
    )

action = sys.argv[1].strip()

if action not in {"UPDATE", "VERIFY_CLOSED"}:
    fail(
        "action must be UPDATE or VERIFY_CLOSED"
    )


services_dir = Path("config/services")
catalog_path = Path(
    "config/estate-updater-catalog.json"
)

if not services_dir.is_dir():
    fail("config/services directory missing")

if not catalog_path.is_file():
    fail("estate updater catalog missing")


with catalog_path.open(
    encoding="utf-8"
) as handle:
    catalog = json.load(handle)


if catalog.get("artifact") != "estate-updater-catalog":
    fail("unexpected estate updater catalog artifact")


catalog_hosts = catalog.get("hosts", {})
catalog_services = catalog.get("services", {})

choices = []


for path in sorted(
    services_dir.glob("*.json")
):
    if not SAFE_MANIFEST.fullmatch(path.name):
        fail(
            f"unsafe reviewed manifest filename: "
            f"{path.name}"
        )

    with path.open(
        encoding="utf-8"
    ) as handle:
        manifest = json.load(handle)

    service = str(
        manifest.get(
            "service", {}
        ).get(
            "name", ""
        )
    )

    host = str(
        manifest.get(
            "service", {}
        ).get(
            "host", ""
        )
    )

    rollback = str(
        manifest.get(
            "versions", {}
        ).get(
            "rollback", {}
        ).get(
            "version", ""
        )
    )

    candidate = str(
        manifest.get(
            "versions", {}
        ).get(
            "candidate", {}
        ).get(
            "version", ""
        )
    )

    if not SAFE_SERVICE.fullmatch(service):
        fail(
            f"{path.name}: unsafe service name"
        )

    if not host:
        fail(
            f"{path.name}: host missing"
        )

    if not rollback or not candidate:
        fail(
            f"{path.name}: version identity missing"
        )

    host_catalog = catalog_hosts.get(host)

    if not isinstance(
        host_catalog,
        dict,
    ):
        continue

    if (
        host_catalog.get(
            "backend_available"
        )
        is not True
    ):
        continue

    service_catalog = (
        catalog_services.get(service)
    )

    if not isinstance(
        service_catalog,
        dict,
    ):
        continue

    estate = (
        service_catalog
        .get("hosts", {})
        .get(host)
    )

    if not isinstance(
        estate,
        dict,
    ):
        continue

    current = estate.get(
        "current_version"
    )

    if current is None:
        continue

    current = str(current)

    if action == "UPDATE":
        eligible = (
            current == rollback
            and candidate != current
        )
    else:
        eligible = (
            current == candidate
        )

    if not eligible:
        continue

    label = (
        f"{service} | {host} | "
        f"{rollback} -> {candidate}"
    )

    choices.append(
        {
            "label": label,
            "manifest": path.name,
            "service": service,
            "host": host,
            "catalog_current_version": current,
            "rollback_version": rollback,
            "candidate_version": candidate,
        }
    )


if not choices:
    fail(
        f"no current-estate reviewed manifests "
        f"available for {action}"
    )


labels = [
    item["label"]
    for item in choices
]

manifests = [
    item["manifest"]
    for item in choices
]


if len(labels) != len(set(labels)):
    fail(
        "current-estate selector labels "
        "are not unique"
    )


if len(manifests) != len(set(manifests)):
    fail(
        "current-estate manifest filenames "
        "are not unique"
    )


document = {
    "schema_version": 1,
    "artifact":
        "stage6-reviewed-manifest-selector",
    "result":
        "current-estate-reviewed-choices-derived",
    "action": action,
    "count": len(choices),
    "choices": choices,
}


print(
    json.dumps(
        document,
        indent=2,
        sort_keys=True,
    )
)
