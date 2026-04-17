#!/usr/bin/env bash
# install-vault-theme.sh — Install kroki-theme.css into a vault's snippets dir.
#
# Usage:
#   install-vault-theme.sh <vault-root>
#
# Default vault-root: ~/Documents/Obsidian Vault
#
# Copies <repo>/styles/kroki-theme.css to <vault-root>/.obsidian/snippets/kroki-theme.css.
# Idempotent: skips copy when contents match.
# Creates .obsidian/snippets/ if absent.
#
# Exit codes:
#   0 — installed or already up-to-date
#   1 — vault-root missing or source CSS missing

set -euo pipefail

VAULT_ROOT="${1:-$HOME/Documents/Obsidian Vault}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_CSS="$REPO_ROOT/styles/kroki-theme.css"
TARGET_DIR="$VAULT_ROOT/.obsidian/snippets"
TARGET_CSS="$TARGET_DIR/kroki-theme.css"

if [[ ! -d "$VAULT_ROOT" ]]; then
    echo "Error: vault root does not exist: $VAULT_ROOT" >&2
    exit 1
fi

if [[ ! -f "$SOURCE_CSS" ]]; then
    echo "Error: source CSS missing: $SOURCE_CSS" >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"

if [[ -f "$TARGET_CSS" ]] && cmp -s "$SOURCE_CSS" "$TARGET_CSS"; then
    echo "OK: kroki-theme.css already up-to-date at $TARGET_CSS"
else
    cp "$SOURCE_CSS" "$TARGET_CSS"
    echo "Installed: $TARGET_CSS"
fi

cat <<EOF

Next step: open Obsidian -> Settings -> Appearance -> CSS snippets,
and toggle "kroki-theme" on. This activates the dual-render theme switcher.
EOF
