#!/usr/bin/env bash
# kroki-autosave.sh — thin CLI wrapper for lib/kroki_autosave/restore.py.
# Symlinked to ~/.local/bin/kroki-autosave by install.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PLUGIN_ROOT"
exec python3 -m lib.kroki_autosave.restore "$@"
