#!/usr/bin/env bash
# version-check.sh — thin bash wrapper for lib/kroki_container/version_check.py.
# Systemd timer target (cycle mode: no args); also a user-facing CLI (subcommands).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PLUGIN_ROOT"
exec python3 -m lib.kroki_container.version_check "$@"
