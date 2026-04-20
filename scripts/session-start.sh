#!/usr/bin/env bash
# session-start.sh — kroki-session mode=start dispatcher.
#
# Usage: session-start.sh [--auto] --project <name> [--vault-path <path>]
#
# --auto marks this as an INSTALLER-driven invocation (gates KROKI_SESSION_AUTO env var).
# Explicit (no --auto) invocations ignore the env var and always run.
set -euo pipefail
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:-}:${PLUGIN_ROOT}"
exec python3 -m lib.kroki_session.start "$@"
