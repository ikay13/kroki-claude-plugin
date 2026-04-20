#!/usr/bin/env bash
# session-snapshot.sh — kroki-session milestone composite dispatcher.
#
# Usage: session-snapshot.sh --project <name> --milestone-label <label> [--vault-path <path>]
set -euo pipefail
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:-}:${PLUGIN_ROOT}"
exec python3 -m lib.kroki_session.snapshot "$@"
