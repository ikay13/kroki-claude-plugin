#!/usr/bin/env bash
# session-end.sh — kroki-session mode=end dispatcher.
#
# Usage: session-end.sh [--auto] --project <name> [--milestone-label <label>] [--vault-path <path>]
#
# --auto marks this as an INSTALLER-driven invocation (gates KROKI_SESSION_AUTO env var).
set -euo pipefail
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:-}:${PLUGIN_ROOT}"
exec python3 -m lib.kroki_session.end "$@"
