#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-/home/james/docker}"
GITIGNORE="$REPO/.gitignore"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/var/tmp/docker-gitignore-${STAMP}.bak"

if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: not a Git worktree: $REPO" >&2
    exit 1
fi

[[ -f "$GITIGNORE" ]] || {
    echo "ERROR: missing .gitignore: $GITIGNORE" >&2
    exit 1
}

install -m 0600 "$GITIGNORE" "$BACKUP"
echo "Backup: $BACKUP"

MARKER="# Generated operational backup and autosync artifacts"

if ! grep -Fqx "$MARKER" "$GITIGNORE"; then
    cat >>"$GITIGNORE" <<'IGNORE'

# Generated operational backup and autosync artifacts
*.bak
*.bak-*
*.backup
*.backup-*
*.pre-*
*.autosync-*

# Archived deployed portfolio trees
/stacks/engineering-portfolio-backup-*/
/stacks/engineering-portfolio-old-*/
IGNORE
    echo "Ignore rules added."
else
    echo "Ignore rules already present; no duplicate block added."
fi

echo
echo "===== GITIGNORE DIFF ====="
git -C "$REPO" diff -- .gitignore

echo
echo "===== STATUS COUNTS AFTER HYGIENE ====="
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
echo "===== REMAINING UNTRACKED FILES ====="
git -C "$REPO" ls-files --others --exclude-standard

echo
echo "No files were deleted, staged or committed."
