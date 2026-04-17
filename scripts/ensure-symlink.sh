#!/usr/bin/env bash
# ensure-symlink.sh — Create or verify vault-to-repo diagrams/ symlink.
#
# Usage:
#   ensure-symlink.sh <repo-dir> <vault-project-dir>
#
# Effect:
#   Creates symlink at <vault-project-dir>/diagrams -> <repo-dir>/diagrams
#   Idempotent: if correct symlink already exists, exits 0.
#   Never clobbers existing files or differently-targeted symlinks.
#
# Exit codes:
#   0 — symlink correct or newly created
#   1 — symlink points elsewhere, or target exists as file/dir
#   3 — usage error

set -euo pipefail

usage() {
    cat <<EOF
Usage: ensure-symlink.sh <repo-dir> <vault-project-dir>

Creates <vault-project-dir>/diagrams as a symlink to <repo-dir>/diagrams.
Idempotent. Errors if a non-symlink file or dir already occupies the target.
EOF
    exit 3
}

if [[ $# -ne 2 ]]; then
    usage
fi

REPO_DIR="$1"
VAULT_PROJECT_DIR="$2"

if [[ ! -d "$REPO_DIR" ]]; then
    echo "Error: repo dir does not exist: $REPO_DIR" >&2
    exit 3
fi

REPO_DIAGRAMS="$REPO_DIR/diagrams"
if [[ ! -d "$REPO_DIAGRAMS" ]]; then
    echo "Error: repo diagrams dir missing: $REPO_DIAGRAMS" >&2
    exit 3
fi

if [[ ! -d "$VAULT_PROJECT_DIR" ]]; then
    echo "Error: vault project dir does not exist: $VAULT_PROJECT_DIR" >&2
    exit 3
fi

TARGET="$VAULT_PROJECT_DIR/diagrams"
EXPECTED="$(readlink -f "$REPO_DIAGRAMS")"

if [[ -L "$TARGET" ]]; then
    current="$(readlink -f "$TARGET")"
    if [[ "$current" == "$EXPECTED" ]]; then
        echo "OK: symlink already correct: $TARGET -> $current"
        exit 0
    else
        echo "Error: symlink points to wrong target: $TARGET -> $current (expected $EXPECTED)" >&2
        exit 1
    fi
elif [[ -e "$TARGET" ]]; then
    echo "Error: $TARGET exists but is not a symlink" >&2
    exit 1
fi

ln -s "$REPO_DIAGRAMS" "$TARGET"
echo "Created: $TARGET -> $REPO_DIAGRAMS"
