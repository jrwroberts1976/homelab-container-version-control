#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-/home/james/docker}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/var/tmp/docker-version-reconcile-${STAMP}"

declare -A FILES=(
    [dozzle]="stacks/management/docker-compose.yml"
    [librespeed]="stacks/availability/docker-compose.yml"
    [homepage]="stacks/dashboards/docker-compose.yml"
)

declare -A OLD=(
    [dozzle]="amir20/dozzle:v10.7.1"
    [librespeed]="ghcr.io/librespeed/speedtest:6.1.0"
    [homepage]="ghcr.io/gethomepage/homepage:v1.12.2"
)

declare -A NEW=(
    [dozzle]="amir20/dozzle:v10.7.2"
    [librespeed]="ghcr.io/librespeed/speedtest:6.2.1"
    [homepage]="ghcr.io/gethomepage/homepage:v2.0.0"
)

if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: not a Git worktree: $REPO" >&2
    exit 1
fi

install -d -m 0700 "$BACKUP_DIR"

echo "===== PREFLIGHT ====="

for service in dozzle librespeed homepage; do
    relative="${FILES[$service]}"
    file="$REPO/$relative"
    old="${OLD[$service]}"
    new="${NEW[$service]}"

    [[ -f "$file" ]] || {
        echo "ERROR: missing Compose file: $file" >&2
        exit 1
    }

    count="$(grep -Fxc "    image: $old" "$file" || true)"

    if [[ "$count" != "1" ]]; then
        echo "ERROR: expected exactly one declaration for $old in $file; found $count" >&2
        exit 1
    fi

    running_reference="$(
        docker inspect "$service" --format '{{.Config.Image}}' 2>/dev/null
    )" || {
        echo "ERROR: running container unavailable: $service" >&2
        exit 1
    }

    if [[ "$running_reference" != "$new" ]]; then
        echo "ERROR: $service is running from $running_reference, expected $new" >&2
        exit 1
    fi

    state="$(
        docker inspect "$service" --format '{{.State.Status}}' 2>/dev/null
    )"

    if [[ "$state" != "running" ]]; then
        echo "ERROR: $service state is $state, expected running" >&2
        exit 1
    fi

    install -m 0600 "$file" "$BACKUP_DIR/${service}-docker-compose.yml"

    printf '%-12s %s -> %s\n' "$service" "$old" "$new"
done

echo
echo "Backups: $BACKUP_DIR"

echo
echo "===== APPLY NARROW RECONCILIATION ====="

for service in dozzle librespeed homepage; do
    file="$REPO/${FILES[$service]}"
    old="${OLD[$service]}"
    new="${NEW[$service]}"

    sed -i "s#    image: ${old}#    image: ${new}#" "$file"
    echo "Updated: ${FILES[$service]}"
done

echo
echo "===== VALIDATE COMPOSE ====="

for service in dozzle librespeed homepage; do
    file="$REPO/${FILES[$service]}"

    docker compose --file "$file" config --quiet
    echo "Valid: ${FILES[$service]}"
done

echo
echo "===== VERIFY DECLARED VERSIONS ====="

for service in dozzle librespeed homepage; do
    file="$REPO/${FILES[$service]}"

    declared="$(
        docker compose --file "$file" config --format json |
        jq -er --arg service "$service" '.services[$service].image'
    )"

    printf '%-12s %s\n' "$service" "$declared"

    if [[ "$declared" != "${NEW[$service]}" ]]; then
        echo "ERROR: validation mismatch for $service" >&2
        exit 1
    fi
done

echo
echo "===== IMAGE-ONLY DIFF ====="

git -C "$REPO" diff --unified=0 --     "${FILES[dozzle]}"     "${FILES[librespeed]}"     "${FILES[homepage]}" |
grep -E '^(diff --git|--- |\+\+\+ |@@|[-+][[:space:]]+image:)' ||
true

echo
echo "Reconciliation completed without restarting containers."
echo "No files were staged or committed."
