#!/usr/bin/env bash
# autosave-daemon.sh — thin bash wrapper for lib/kroki_autosave/daemon.py.
# Systemd ExecStart target (no args needed); dispatches to Python entry point.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PLUGIN_ROOT"
exec python3 -m lib.kroki_autosave.daemon "$@"
