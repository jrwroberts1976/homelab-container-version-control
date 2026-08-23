#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-/home/james/docker}"
REPORT="${2:-/var/tmp/docker-baseline-assessment.txt}"

if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: not a Git worktree: $REPO" >&2
    exit 1
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

mapfile -t changed < <(
    {
        git -C "$REPO" diff --name-only
        git -C "$REPO" ls-files --others --exclude-standard
    } |
    sort -u
)

{
    echo "===== DOCKER BASELINE ASSESSMENT ====="
    echo "Generated: $(date --iso-8601=seconds)"
    echo "Repository: $(git -C "$REPO" rev-parse --show-toplevel)"
    echo "Branch: $(git -C "$REPO" branch --show-current)"
    echo "HEAD: $(git -C "$REPO" rev-parse HEAD)"

    echo
    echo "===== STATUS ====="
    git -C "$REPO" status --short

    echo
    echo "===== CHANGE TYPE SUMMARY ====="
    git -C "$REPO" status --porcelain=v1 -uall |
        awk '
          {
            code = substr($0, 1, 2)
            counts[code]++
            total++
          }
          END {
            print "Total:", total + 0
            for (code in counts) {
              printf "%s %d\n", code, counts[code]
            }
          }
        ' |
        sort

    echo
    echo "===== TRACKED DIFF STAT BY FILE ====="
    git -C "$REPO" diff --numstat

    echo
    echo "===== TRACKED DELETIONS ====="
    git -C "$REPO" diff --diff-filter=D --name-only |
        while IFS= read -r path; do
            [[ -n "$path" ]] || continue
            printf '%s\tlast changed: ' "$path"
            git -C "$REPO" log -1 --format='%h %cs %s' -- "$path"
        done

    echo
    echo "===== UNTRACKED FILE METADATA ====="
    git -C "$REPO" ls-files --others --exclude-standard |
        while IFS= read -r path; do
            [[ -n "$path" ]] || continue
            if [[ -d "$REPO/$path" ]]; then
                printf 'directory\t%s\n' "$path"
            elif [[ -f "$REPO/$path" ]]; then
                size="$(stat -c %s "$REPO/$path")"
                type="$(file -b "$REPO/$path")"
                printf 'file\t%s\t%s bytes\t%s\n' "$path" "$size" "$type"
            fi
        done

    echo
    echo "===== NESTED GIT WORKTREES ====="
    find "$REPO" -path "$REPO/.git" -prune -o \
        -type d -name .git -print 2>/dev/null |
        sed "s#^$REPO/##" |
        sort

    echo
    echo "===== DUPLICATE MAINTENANCE SCRIPT CHECK ====="
    for name in enable-maintenance.sh disable-maintenance.sh; do
        root_script="$REPO/scripts/$name"
        stack_script="$REPO/stacks/maintenance-page/$name"

        if [[ -f "$root_script" && -f "$stack_script" ]]; then
            if cmp -s "$root_script" "$stack_script"; then
                echo "$name: IDENTICAL"
            else
                echo "$name: DIFFERENT"
                diff --brief "$root_script" "$stack_script" || true
            fi
        else
            echo "$name: one or both copies missing"
        fi
    done

    echo
    echo "===== COMPOSE VALIDATION ====="
    for path in "${changed[@]}"; do
        case "${path##*/}" in
            compose.yml|compose.yaml|docker-compose.yml|docker-compose.yaml)
                if [[ ! -f "$REPO/$path" ]]; then
                    continue
                fi

                if docker compose --file "$REPO/$path" config --quiet >/dev/null 2>&1; then
                    echo "PASS $path"
                else
                    echo "FAIL $path"
                fi
                ;;
        esac
    done

    echo
    echo "===== POSSIBLE SECRET ASSIGNMENTS (VALUES REDACTED) ====="
    for path in "${changed[@]}"; do
        [[ -f "$REPO/$path" ]] || continue

        case "$path" in
            *.yml|*.yaml|*.env|*.json|*.conf|*.py|*.sh|Dockerfile|*/Dockerfile)
                grep -nEi \
                    '(^|[^A-Za-z])(password|passwd|token|api[_-]?key|secret|private[_-]?key)[[:space:]]*[:=]' \
                    "$REPO/$path" 2>/dev/null |
                sed -E 's#([:=])[[:space:]]*.*#\1 <redacted>#' |
                sed "s#^#$path:#" ||
                true
                ;;
        esac
    done

    echo
    echo "===== REPOSITORY SECRET-NAME FILES ====="
    git -C "$REPO" ls-files --others --exclude-standard |
        grep -Ei '(^|/)(\.env|.*secret.*|.*credential.*|.*token.*|.*\.key|.*\.pem)$' ||
        true

    echo
    echo "===== CURRENT GITIGNORE DIFF ====="
    git -C "$REPO" diff -- .gitignore

    echo
    echo "No files were changed, staged, deleted or committed by this assessment."
} >"$TMP"

install -m 0600 "$TMP" "$REPORT"
echo "$REPORT"
