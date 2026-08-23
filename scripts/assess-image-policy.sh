#!/usr/bin/env bash
set -euo pipefail

INPUT="${1:-}"

if [[ -z "$INPUT" || ! -r "$INPUT" ]]; then
    echo "Usage: $0 <container-inventory.tsv>" >&2
    exit 1
fi

awk -F '\t' '
BEGIN {
    OFS = "\t"
}

NR == 1 {
    expected[1] = "host"
    expected[2] = "container"
    expected[3] = "compose_project"
    expected[4] = "compose_service"
    expected[5] = "compose_files"
    expected[6] = "desired_image"
    expected[7] = "creation_image"
    expected[8] = "running_image_id"
    expected[9] = "running_repo_digests"
    expected[10] = "management"
    expected[11] = "version_policy"
    expected[12] = "drift"

    if (NF < 12) {
        print "ERROR: inventory header has fewer than 12 fields" > "/dev/stderr"
        exit 2
    }

    for (i = 1; i <= 12; i++) {
        if ($i != expected[i]) {
            print "ERROR: unexpected inventory field " i ": " $i > "/dev/stderr"
            exit 2
        }
    }

    print $0, "compliance_state", "compliance_reason"
    next
}

{
    state = "policy-review"
    reason = "Inventory classification requires policy review"

    if ($10 == "unmanaged") {
        state = "unmanaged"
        reason = "No authoritative Compose management source"
    } else if ($11 == "local-build" || $10 == "compose:local-build") {
        state = "local-build-unverified"
        reason = "Assess source revision and OCI provenance separately"
    } else if ($12 != "no") {
        state = "drift"
        reason = "Runtime does not match authoritative desired state"
    } else if ($11 == "floating") {
        state = "exception-required"
        reason = "Floating image reference requires approval or pinning"
    } else if ($11 == "digest-pinned") {
        state = "compliant-digest"
        reason = "Immutable digest declaration and no detected drift"
    } else if ($11 == "version-tagged") {
        state = "compliant-version-tag"
        reason = "Explicit version tag and no detected drift"
    }

    print $0, state, reason
}
' "$INPUT"
