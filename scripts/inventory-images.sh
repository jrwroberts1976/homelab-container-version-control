#!/usr/bin/env bash
set -euo pipefail

HOST_LABEL="${1:-$(hostname -s)}"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is required." >&2
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker is unavailable to the current user." >&2
    exit 1
fi

sanitize() {
    printf '%s' "$1" | tr '\t\r\n' '   '
}

is_floating() {
    local reference="$1"
    local without_digest tag

    without_digest="${reference%@*}"

    if [[ "$reference" == *@sha256:* ]]; then
        return 1
    fi

    if [[ "$without_digest" != *:* ]] || \
       [[ "${without_digest##*/}" != *:* ]]; then
        return 0
    fi

    tag="${without_digest##*:}"

    case "${tag,,}" in
        latest|stable|edge|nightly|dev|develop|development|main|master)
            return 0
            ;;
    esac

    return 1
}

compose_declared_image() {
    local service="$1"
    local config_files="$2"
    local working_dir="$3"
    local -a args=()
    local file config_json

    [[ -n "$service" && -n "$config_files" ]] || return 1

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue

        if [[ "$file" != /* && -n "$working_dir" ]]; then
            file="$working_dir/$file"
        fi

        [[ -r "$file" ]] || return 1
        args+=(--file "$file")
    done < <(printf '%s\n' "$config_files" | tr ',' '\n')

    (("${#args[@]}" > 0)) || return 1

    if [[ -n "$working_dir" && -d "$working_dir" ]]; then
        config_json="$(
            cd "$working_dir"
            docker compose "${args[@]}" config --format json 2>/dev/null
        )" || return 1
    else
        config_json="$(
            docker compose "${args[@]}" config --format json 2>/dev/null
        )" || return 1
    fi

    jq -er --arg service "$service" \
        '.services[$service] |
         if .image then .image
         elif .build then "__LOCAL_BUILD__"
         else empty
         end' \
        <<<"$config_json"
}

printf '%s\n' \
    $'host\tcontainer\tcompose_project\tcompose_service\tcompose_files\tdesired_image\tcreation_image\trunning_image_id\trunning_repo_digests\tmanagement\tversion_policy\tdrift'

mapfile -t containers < <(docker ps -aq --no-trunc | sort)

for container_id in "${containers[@]}"; do
    inspect="$(docker inspect "$container_id")"

    container="$(
        jq -r '.[0].Name | ltrimstr("/")' <<<"$inspect"
    )"
    project="$(
        jq -r '.[0].Config.Labels["com.docker.compose.project"] // ""' \
            <<<"$inspect"
    )"
    service="$(
        jq -r '.[0].Config.Labels["com.docker.compose.service"] // ""' \
            <<<"$inspect"
    )"
    config_files="$(
        jq -r '.[0].Config.Labels["com.docker.compose.project.config_files"] // ""' \
            <<<"$inspect"
    )"
    working_dir="$(
        jq -r '.[0].Config.Labels["com.docker.compose.project.working_dir"] // ""' \
            <<<"$inspect"
    )"
    creation_image="$(
        jq -r '.[0].Config.Image // ""' <<<"$inspect"
    )"
    running_image_id="$(
        jq -r '.[0].Image // ""' <<<"$inspect"
    )"

    desired_image="$creation_image"
    declaration_source="runtime-creation"

    if resolved="$(
        compose_declared_image "$service" "$config_files" "$working_dir"
    )"; then
        if [[ "$resolved" == "__LOCAL_BUILD__" ]]; then
            desired_image="$creation_image"
            declaration_source="local-build"
        else
            desired_image="$resolved"
            declaration_source="compose"
        fi
    fi

    if [[ -n "$project" && -n "$service" ]]; then
        management="compose:${declaration_source}"
    else
        management="unmanaged"
    fi

    if [[ "$declaration_source" == "local-build" ]]; then
        version_policy="local-build"
    elif is_floating "$desired_image"; then
        version_policy="floating"
    elif [[ "$desired_image" == *@sha256:* ]]; then
        version_policy="digest-pinned"
    else
        version_policy="version-tagged"
    fi

    repo_digests="$(
        docker image inspect "$running_image_id" \
            --format '{{json .RepoDigests}}' 2>/dev/null |
        jq -r '(. // []) | join(",")' 2>/dev/null ||
        true
    )"

    drift="unknown"

    desired_normalized="$desired_image"
    creation_normalized="$creation_image"

    if [[ "${desired_normalized##*/}" != *:* ]] &&
       [[ "$desired_normalized" != *@* ]]; then
        desired_normalized="${desired_normalized}:latest"
    fi

    if [[ "${creation_normalized##*/}" != *:* ]] &&
       [[ "$creation_normalized" != *@* ]]; then
        creation_normalized="${creation_normalized}:latest"
    fi

    if [[ "$declaration_source" == "local-build" ]]; then
        drift="not-assessed-local-build"
    elif [[ "$desired_normalized" != "$creation_normalized" ]]; then
        drift="yes-reference"
    elif desired_id="$(
        docker image inspect "$desired_image" \
            --format '{{.Id}}' 2>/dev/null
    )"; then
        if [[ "$desired_id" == "$running_image_id" ]]; then
            drift="no"
        else
            drift="yes-image"
        fi
    else
        drift="not-locally-resolvable"
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$(sanitize "$HOST_LABEL")" \
        "$(sanitize "$container")" \
        "$(sanitize "$project")" \
        "$(sanitize "$service")" \
        "$(sanitize "$config_files")" \
        "$(sanitize "$desired_image")" \
        "$(sanitize "$creation_image")" \
        "$(sanitize "$running_image_id")" \
        "$(sanitize "$repo_digests")" \
        "$(sanitize "$management")" \
        "$(sanitize "$version_policy")" \
        "$(sanitize "$drift")"
done
