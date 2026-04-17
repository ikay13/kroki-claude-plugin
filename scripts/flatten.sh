#!/usr/bin/env bash
# flatten.sh — Replace var(--name, fallback) refs with their fallback hex.
#
# Usage:
#   flatten.sh <input.svg> <output.svg>
#
# Wraps lib/kroki_util.flatten_css_vars(). Writes output atomically.
#
# Exit codes:
#   0 — ok
#   1 — input missing or I/O error
#   2 — usage error

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: flatten.sh <input.svg> <output.svg>" >&2
    exit 2
fi

SRC="$1"
OUT="$2"

if [[ ! -f "$SRC" ]]; then
    echo "Error: input missing: $SRC" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 "$REPO_ROOT/lib/kroki_util.py" --op flatten --in "$SRC" --out "$OUT"
