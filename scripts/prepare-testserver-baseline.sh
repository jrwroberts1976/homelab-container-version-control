#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-/home/james/docker}"
BRANCH="${2:-baseline/testserver-20260823}"
STAMP="$(date +%Y%m%d-%H%M%S)"
EVIDENCE_DIR="/var/tmp/docker-baseline-${STAMP}"

TRACKED_PATHS=(
    .gitignore
    stacks/availability/docker-compose.yml
    stacks/birdnet-go/docker-compose.yaml
    stacks/cloudflare-ddns/docker-compose.yml
    stacks/crowdsec/docker-compose.yml
    stacks/dashboards/docker-compose.yml
    stacks/maintenance-page/docker-compose.yml
    stacks/maintenance-page/html/index.html
    stacks/management/docker-compose.yml
    stacks/monitoring/asus-exporter/exporter.py
    stacks/monitoring/docker-compose.yml
    stacks/proxy-auth/docker-compose.yml
    stacks/training-platform/docs/courses/docker/index.md
    stacks/training-platform/docs/training/course-statistics.md
    stacks/training-platform/docs/training/index.md
    stacks/training-platform/docs/training/learning-paths.md
    stacks/training-platform/docs/training/recent-updates.md
    stacks/training-platform/docs/training/skill-matrix.md
)

NEW_PATHS=(
    stacks/alloy/docker-compose.yml
    stacks/maintenance-page/disable-maintenance.sh
    stacks/maintenance-page/enable-maintenance.sh
    stacks/maintenance-page/nginx/default.conf
    stacks/training-platform/.gitignore
    stacks/wud/docker-compose.yml
)

ARCHIVE_PATHS=(
    scripts/disable-maintenance.sh
    scripts/enable-maintenance.sh
    stacks/jenkins/Dockerfile
    stacks/jenkins/docker-compose.yml
)

if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: not a Git worktree: $REPO" >&2
    exit 1
fi

if [[ -n "$(git -C "$REPO" diff --cached --name-only)" ]]; then
    echo "ERROR: staged changes already exist; refusing to mix baselines." >&2
    exit 1
fi

install -d -m 0700 "$EVIDENCE_DIR"

git -C "$REPO" diff --binary >"$EVIDENCE_DIR/tracked-changes.patch"
git -C "$REPO" status --short >"$EVIDENCE_DIR/status-before.txt"

for relative in "${ARCHIVE_PATHS[@]}"; do
    source="$REPO/$relative"

    if [[ -e "$source" ]]; then
        destination="$EVIDENCE_DIR/archived/$relative"
        install -d -m 0700 "$(dirname "$destination")"
        cp -a "$source" "$destination"
    fi
done

echo "Evidence and archived files: $EVIDENCE_DIR"

if git -C "$REPO" show-ref --verify --quiet "refs/heads/$BRANCH"; then
    current="$(git -C "$REPO" branch --show-current)"

    if [[ "$current" != "$BRANCH" ]]; then
        echo "ERROR: branch already exists: $BRANCH" >&2
        exit 1
    fi
else
    git -C "$REPO" switch -c "$BRANCH"
fi

GITIGNORE="$REPO/.gitignore"

if ! grep -Fqx "# Local deployment checkouts and runtime state" "$GITIGNORE"; then
    cat >>"$GITIGNORE" <<'IGNORE'

# Local deployment checkouts and runtime state
/stacks/engineering-portfolio-git/
/stacks/maintenance-page/html/change.json
IGNORE
fi

for relative in "${ARCHIVE_PATHS[@]}"; do
    target="$REPO/$relative"

    if [[ -f "$target" ]]; then
        rm -- "$target"
    fi
done

rmdir "$REPO/stacks/jenkins" 2>/dev/null || true

echo
echo "===== VALIDATE COMPOSE FILES ====="

declare -a compose_paths=()

for relative in "${TRACKED_PATHS[@]}" "${NEW_PATHS[@]}"; do
    case "${relative##*/}" in
        compose.yml|compose.yaml|docker-compose.yml|docker-compose.yaml)
            [[ -f "$REPO/$relative" ]] || continue
            docker compose --file "$REPO/$relative" config --quiet
            echo "PASS $relative"
            compose_paths+=("$relative")
            ;;
    esac
done

git -C "$REPO" add -- "${TRACKED_PATHS[@]}" "${NEW_PATHS[@]}"

echo
echo "===== STAGED PATHS ====="
git -C "$REPO" diff --cached --name-status

echo
echo "===== STAGED DIFF STAT ====="
git -C "$REPO" diff --cached --stat

echo
echo "===== STAGED SECRET-NAME CHECK ====="

secret_names="$(
    git -C "$REPO" diff --cached --name-only |
    grep -Ei '(^|/)(\.env|.*secret.*|.*credential.*|.*token.*|.*\.key|.*\.pem)$' ||
    true
)"

if [[ -n "$secret_names" ]]; then
    echo "ERROR: secret-like staged filenames detected:" >&2
    printf '%s\n' "$secret_names" >&2
    exit 1
fi

echo "No secret-like filenames staged."

echo
echo "===== UNSTAGED/UNTRACKED REMAINDER ====="
git -C "$REPO" status --short |
    grep -E '^( M| D|\?\?| m)' ||
    true

echo
echo "Baseline is staged on branch: $BRANCH"
echo "Nothing was committed or pushed."
