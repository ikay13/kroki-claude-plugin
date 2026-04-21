#!/usr/bin/env bash
# editor-open.sh [source-file] — launch Niolesk, write editor lock.
#
# With source-file: pre-loads Niolesk via encoded URL fragment; lock stores source_path.
# Without:          opens blank Niolesk; lock stores source_path: null (soft-only).
#
# Exits:
#   0  success
#   1  pod down, display unavailable, file not found, disk/permission error
#   2  encoding failure (unknown extension propagated from encode-url.sh)
#   3  lock already held; stderr identifies the held source and stale-at time

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_FILE="${1:-}"

# Display preflight — fail fast before writing a lock we can't use.
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "editor-open.sh: no graphical session detected (\$DISPLAY and \$WAYLAND_DISPLAY both unset)." >&2
    echo "Niolesk requires a local browser. Aborting without writing a lock." >&2
    exit 1
fi

# Pod preflight. If a pod-health.sh is first on PATH (smoke tests stub this), use it;
# otherwise fall back to the one in scripts/.
HEALTH_CMD="$(command -v pod-health.sh 2>/dev/null || true)"
if [[ -z "$HEALTH_CMD" ]]; then
    HEALTH_CMD="$SCRIPT_DIR/pod-health.sh"
fi
if ! "$HEALTH_CMD" >/dev/null 2>&1; then
    echo "editor-open.sh: kroki pod is not healthy. Run 'kroki.sh up' first." >&2
    exit 1
fi

if [[ -n "$SOURCE_FILE" ]]; then
    if [[ ! -f "$SOURCE_FILE" ]]; then
        echo "editor-open.sh: file not found: $SOURCE_FILE" >&2
        exit 1
    fi
    KROKI_URL="$("$SCRIPT_DIR/encode-url.sh" "$SOURCE_FILE")" || exit $?
    NIOLESK_URL="http://localhost:8017/#${KROKI_URL}"
    ABS_SOURCE="$(realpath "$SOURCE_FILE")"
    (cd "$PLUGIN_ROOT" && python3 -m lib.kroki_session.lock open --source "$ABS_SOURCE") || exit $?
else
    NIOLESK_URL="http://localhost:8017/"
    (cd "$PLUGIN_ROOT" && python3 -m lib.kroki_session.lock open) || exit $?
fi

xdg-open "$NIOLESK_URL" >/dev/null 2>&1 &

if [[ -n "$SOURCE_FILE" ]]; then
    echo "Niolesk opened with $SOURCE_FILE pre-loaded."
else
    echo "Niolesk opened with a blank editor."
fi
echo "When done: click Download in Niolesk, then run scripts/editor-close.sh."
