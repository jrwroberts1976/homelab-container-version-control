#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-/home/james/docker}"
REPORT="${2:-/var/tmp/docker-worktree-audit.txt}"

if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required." >&2
    exit 1
fi

if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: not a Git worktree: $REPO" >&2
    exit 1
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

{
    echo "===== DOCKER WORKTREE AUDIT ====="
    echo "Generated: $(date --iso-8601=seconds)"
    echo "Repository: $(git -C "$REPO" rev-parse --show-toplevel)"
    echo "Branch: $(git -C "$REPO" branch --show-current)"
    echo "HEAD: $(git -C "$REPO" rev-parse HEAD)"

    echo
    echo "===== REMOTES ====="
    git -C "$REPO" remote -v || true

    echo
    echo "===== TRACKING STATUS ====="
    branch="$(git -C "$REPO" branch --show-current)"
    upstream="$(git -C "$REPO" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || true)"

    if [[ -n "$upstream" ]]; then
        echo "Upstream: $upstream"
        git -C "$REPO" rev-list --left-right --count "$upstream...HEAD" |
            awk '{print "Behind:", $1, "Ahead:", $2}'
    else
        echo "Upstream: NOT CONFIGURED"
    fi

    echo
    echo "===== STATUS COUNTS ====="
    git -C "$REPO" status --porcelain=v1 -uall |
        awk '
          {
            code = substr($0, 1, 2)
            counts[code]++
            total++
          }
          END {
            print "Total entries:", total + 0
            for (code in counts) {
              printf "%s %d\n", code, counts[code]
            }
          }
        ' |
        sort

    echo
    echo "===== TRACKED MODIFICATIONS ====="
    git -C "$REPO" status --short --untracked-files=no

    echo
    echo "===== UNTRACKED FILE CLASSIFICATION ====="
    git -C "$REPO" ls-files --others --exclude-standard |
        awk '
          /(^|\/)([^\/]*\.bak([^\/]*)?|[^\/]*\.backup([^\/]*)?|[^\/]*\.pre-[^\/]*|[^\/]*\.autosync-[^\/]*)$/ {
            backup++
            next
          }
          /(^|\/)engineering-portfolio-(backup|old)-/ {
            archived_tree++
            next
          }
          {
            operational++
          }
          END {
            print "Backup/autosync artifacts:", backup + 0
            print "Archived trees:", archived_tree + 0
            print "Other operational candidates:", operational + 0
          }
        '

    echo
    echo "===== UNTRACKED OPERATIONAL CANDIDATES ====="
    git -C "$REPO" ls-files --others --exclude-standard |
        grep -Ev '(^|/)([^/]*\.bak([^/]*)?|[^/]*\.backup([^/]*)?|[^/]*\.pre-[^/]*|[^/]*\.autosync-[^/]*)$|(^|/)engineering-portfolio-(backup|old)-' ||
        true

    echo
    echo "===== TARGET COMPOSE DIFFS ====="
    for path in         stacks/management/docker-compose.yml         stacks/availability/docker-compose.yml         stacks/dashboards/docker-compose.yml
    do
        echo
        echo "----- $path"
        git -C "$REPO" diff -- "$path"
    done

    echo
    echo "===== ALL TRACKED DIFF STAT ====="
    git -C "$REPO" diff --stat

    echo
    echo "===== STAGED DIFF STAT ====="
    git -C "$REPO" diff --cached --stat

    echo
    echo "===== IGNORE FILE ====="
    if [[ -r "$REPO/.gitignore" ]]; then
        sed -n '1,260p' "$REPO/.gitignore"
    else
        echo "NO .gitignore"
    fi

    echo
    echo "===== RECENT COMMITS ====="
    git -C "$REPO" log -10 --oneline --decorate
} >"$TMP"

install -m 0644 "$TMP" "$REPORT"

echo "$REPORT"
