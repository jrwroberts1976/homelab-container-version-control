#!/usr/bin/env bash
set -euo pipefail

HOST_LABEL="${1:-$(hostname -s)}"

for command_name in docker jq; do
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

is_sensitive_name() {
    local name="${1^^}"

    [[ "$name" =~ (PASSWORD|PASSWD|TOKEN|SECRET|CREDENTIAL|API_KEY|PRIVATE_KEY|ACCESS_KEY|AUTH_KEY|CLIENT_SECRET) ]]
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
        '.services[$service] // empty' \
        <<<"$config_json"
}

printf '%s\n' \
    $'host\tcontainer\tstate\tcompose_project\tcompose_service\tcompose_files\tsensitive_environment_names\tcompose_secret_sources\tcompose_secret_targets\tsensitive_mounts\tbuild_argument_names\tdelivery_methods'

mapfile -t containers < <(docker ps -aq --no-trunc | sort)

for container_id in "${containers[@]}"; do
    inspect="$(docker inspect "$container_id")"

    container="$(jq -r '.[0].Name | ltrimstr("/")' <<<"$inspect")"
    state="$(jq -r '.[0].State.Status // "unknown"' <<<"$inspect")"
    project="$(jq -r '.[0].Config.Labels["com.docker.compose.project"] // ""' <<<"$inspect")"
    service="$(jq -r '.[0].Config.Labels["com.docker.compose.service"] // ""' <<<"$inspect")"
    config_files="$(jq -r '.[0].Config.Labels["com.docker.compose.project.config_files"] // ""' <<<"$inspect")"
    working_dir="$(jq -r '.[0].Config.Labels["com.docker.compose.project.working_dir"] // ""' <<<"$inspect")"

    sensitive_environment_names=""
    while IFS= read -r env_name; do
        if is_sensitive_name "$env_name"; then
            if [[ -n "$sensitive_environment_names" ]]; then
                sensitive_environment_names+=","
            fi
            sensitive_environment_names+="$env_name"
        fi
    done < <(
        jq -r '.[0].Config.Env[]? | split("=")[0]' <<<"$inspect" |
        sort -u
    )

    sensitive_mounts="$(
        jq -r '
          [
            .[0].Mounts[]? |
            select(
              ((.Source // "") | test("secret|credential|token|password|passwd|\\.env($|\\.)|\\.pem$|\\.key$"; "i")) or
              ((.Destination // "") | test("/run/secrets|secret|credential|token|password|passwd|\\.env($|\\.)|\\.pem$|\\.key$"; "i"))
            ) |
            "\(.Source)->\(.Destination)"
          ] |
          unique |
          join(",")
        ' <<<"$inspect"
    )"

    compose_secret_sources=""
    compose_secret_targets=""
    build_argument_names=""

    if service_json="$(
        compose_service_json "$service" "$config_files" "$working_dir"
    )"; then
        compose_secret_sources="$(
            jq -r '
              [
                .secrets[]? |
                if type == "string" then .
                else (.source // "")
                end
              ] |
              map(select(length > 0)) |
              unique |
              join(",")
            ' <<<"$service_json"
        )"

        compose_secret_targets="$(
            jq -r '
              [
                .secrets[]? |
                if type == "string" then ("/run/secrets/" + .)
                else (.target // ("/run/secrets/" + (.source // "")))
                end
              ] |
              map(select(length > 0)) |
              unique |
              join(",")
            ' <<<"$service_json"
        )"

        build_argument_names="$(
            jq -r '(.build.args // {}) | keys | join(",")' \
                <<<"$service_json"
        )"
    fi

    methods=()
    [[ -n "$sensitive_environment_names" ]] && methods+=(environment)
    [[ -n "$compose_secret_sources" ]] && methods+=(compose-secret)
    [[ -n "$sensitive_mounts" ]] && methods+=(sensitive-mount)
    [[ -n "$build_argument_names" ]] && methods+=(build-arguments)

    if (("${#methods[@]}" == 0)); then
        delivery_methods="none-detected"
    else
        delivery_methods="$(IFS=,; printf '%s' "${methods[*]}")"
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$(sanitize "$HOST_LABEL")" \
        "$(sanitize "$container")" \
        "$(sanitize "$state")" \
        "$(sanitize "$project")" \
        "$(sanitize "$service")" \
        "$(sanitize "$config_files")" \
        "$(sanitize "$sensitive_environment_names")" \
        "$(sanitize "$compose_secret_sources")" \
        "$(sanitize "$compose_secret_targets")" \
        "$(sanitize "$sensitive_mounts")" \
        "$(sanitize "$build_argument_names")" \
        "$(sanitize "$delivery_methods")"
done
