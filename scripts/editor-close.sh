#!/usr/bin/env bash
# editor-close.sh — clear editor lock, remind user about manual save-back.
#
# Exits 0 always (excluding I/O errors, which propagate as 1).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOCK_INFO="$(cd "$PLUGIN_ROOT" && python3 -m lib.kroki_session.lock close)"

if [[ -z "$LOCK_INFO" ]]; then
    echo "No lock was held."
    exit 0
fi

# Extract source_path via python3 (consistent with the rest of the plugin;
# avoids adding jq as a new external dependency).
SRC="$(echo "$LOCK_INFO" | python3 -c 'import sys, json; d=json.load(sys.stdin); print(d.get("source_path") or "")')"

if [[ -n "$SRC" ]]; then
    cat <<EOF
Lock released.

If you edited in Niolesk, click Download and place the file at:
    $SRC

Automated save-back is deferred to a future plan.
EOF
else
    echo "Lock released (blank session)."
fi
