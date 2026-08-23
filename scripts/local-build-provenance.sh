#!/usr/bin/env bash
set -euo pipefail

HOST_LABEL="${1:-$(hostname -s)}"

for command_name in docker jq git sha256sum; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "ERROR: ${command_name} is required." >&2
        exit 1
    fi
done

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker is unavailable to the current user." >&2
    exit 1
fi

sanitize() {
    printf '%s' "$1" | tr '\t\r\n' '   '
}

compose_service_json() {
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

    jq -ce --arg service "$service" \
        '.services[$service] | select(.build != null)' \
        <<<"$config_json"
}

printf '%s\n' \
    $'host\tcontainer\tcompose_project\tcompose_service\tcompose_files\tbuild_context\tdockerfile\tdockerfile_sha256\tbuild_arg_names\tsource_git_root\tsource_git_commit\tsource_dirty\trunning_image_id\timage_created\timage_revision_label\timage_source_label\tassessment\tcontainer_state'

mapfile -t containers < <(docker ps -aq --no-trunc | sort)

for container_id in "${containers[@]}"; do
    inspect="$(docker inspect "$container_id")"

    container="$(jq -r '.[0].Name | ltrimstr("/")' <<<"$inspect")"
    project="$(jq -r '.[0].Config.Labels["com.docker.compose.project"] // ""' <<<"$inspect")"
    service="$(jq -r '.[0].Config.Labels["com.docker.compose.service"] // ""' <<<"$inspect")"
    config_files="$(jq -r '.[0].Config.Labels["com.docker.compose.project.config_files"] // ""' <<<"$inspect")"
    working_dir="$(jq -r '.[0].Config.Labels["com.docker.compose.project.working_dir"] // ""' <<<"$inspect")"
    running_image_id="$(jq -r '.[0].Image // ""' <<<"$inspect")"
    container_state="$(jq -r '.[0].State.Status // "unknown"' <<<"$inspect")"

    if ! service_json="$(
        compose_service_json "$service" "$config_files" "$working_dir"
    )"; then
        continue
    fi

    build_context="$(jq -r '.build.context // ""' <<<"$service_json")"
    dockerfile_value="$(jq -r '.build.dockerfile // "Dockerfile"' <<<"$service_json")"
    build_arg_names="$(jq -r '(.build.args // {}) | keys | join(",")' <<<"$service_json")"

    if [[ -n "$build_context" && "$build_context" != /* && -n "$working_dir" ]]; then
        build_context="$working_dir/$build_context"
    fi

    if [[ "$dockerfile_value" == /* ]]; then
        dockerfile="$dockerfile_value"
    else
        dockerfile="$build_context/$dockerfile_value"
    fi

    dockerfile_sha256=""
    if [[ -r "$dockerfile" ]]; then
        dockerfile_sha256="$(sha256sum "$dockerfile" | awk '{print $1}')"
    fi

    source_git_root=""
    source_git_commit=""
    source_dirty="unknown"

    if [[ -d "$build_context" ]] && \
       source_git_root="$(git -C "$build_context" rev-parse --show-toplevel 2>/dev/null)"; then
        source_git_commit="$(git -C "$source_git_root" rev-parse HEAD 2>/dev/null || true)"
        context_relative="$(realpath --relative-to="$source_git_root" "$build_context" 2>/dev/null || printf '.')"

        if [[ -n "$(git -C "$source_git_root" status --porcelain --untracked-files=normal -- "$context_relative" 2>/dev/null)" ]]; then
            source_dirty="yes"
        else
            source_dirty="no"
        fi
    fi

    image_json="$(docker image inspect "$running_image_id")"
    image_created="$(jq -r '.[0].Created // ""' <<<"$image_json")"
    image_revision="$(jq -r '.[0].Config.Labels["org.opencontainers.image.revision"] // ""' <<<"$image_json")"
    image_source="$(jq -r '.[0].Config.Labels["org.opencontainers.image.source"] // ""' <<<"$image_json")"

    if [[ -z "$source_git_root" ]]; then
        assessment="no-git-source"
    elif [[ "$source_dirty" == "yes" ]]; then
        assessment="source-dirty"
    elif [[ -z "$image_revision" ]]; then
        assessment="unverified-no-revision-label"
    elif [[ "$source_git_commit" == "$image_revision" || "$source_git_commit" == "$image_revision"* ]]; then
        assessment="revision-match"
    else
        assessment="revision-mismatch"
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$(sanitize "$HOST_LABEL")" \
        "$(sanitize "$container")" \
        "$(sanitize "$project")" \
        "$(sanitize "$service")" \
        "$(sanitize "$config_files")" \
        "$(sanitize "$build_context")" \
        "$(sanitize "$dockerfile")" \
        "$(sanitize "$dockerfile_sha256")" \
        "$(sanitize "$build_arg_names")" \
        "$(sanitize "$source_git_root")" \
        "$(sanitize "$source_git_commit")" \
        "$(sanitize "$source_dirty")" \
        "$(sanitize "$running_image_id")" \
        "$(sanitize "$image_created")" \
        "$(sanitize "$image_revision")" \
        "$(sanitize "$image_source")" \
        "$(sanitize "$assessment")" \
        "$(sanitize "$container_state")"
done
