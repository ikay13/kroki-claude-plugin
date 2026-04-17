#!/usr/bin/env bash
# pod-health.sh — Check Kroki pod health, auto-start if down, escalate if broken.
#
# Exit codes:
#   0 — pod is healthy and responding
#   1 — pod could not be made healthy after recovery attempts
#
# Stdout: status messages for Claude to relay to user
# Stderr: diagnostic detail for logging
#
# Circuit breaker: after 2 failed restart attempts within 10 minutes,
# writes ~/.kroki-plugin/.pod-circuit-open and exits 1 on all subsequent calls.

set -euo pipefail

KROKI_ENDPOINT="${KROKI_ENDPOINT:-http://localhost:8000}"
KROKI_SH="${KROKI_SH:-$HOME/kroki/kroki.sh}"
STATE_DIR="${KROKI_STATE_DIR:-$HOME/.kroki-plugin}"
CIRCUIT_FILE="$STATE_DIR/.pod-circuit-open"
RESTART_COUNT_FILE="$STATE_DIR/.pod-restart-count"
LAST_USE_FILE="$STATE_DIR/.last-use"
MAX_RESTARTS=2
CIRCUIT_WINDOW=600  # 10 minutes in seconds
HEALTH_TIMEOUT=5
STARTUP_POLL_INTERVAL=2
STARTUP_POLL_MAX=15  # 15 polls * 2s = 30s max wait

mkdir -p "$STATE_DIR"

# Touch last-use for watchdog idle detection
date +%s > "$LAST_USE_FILE"

# Check circuit breaker
if [[ -f "$CIRCUIT_FILE" ]]; then
    circuit_ts=$(cat "$CIRCUIT_FILE" 2>/dev/null || echo 0)
    now=$(date +%s)
    # Clear circuit on new session (>10 min since circuit opened)
    if (( now - circuit_ts > CIRCUIT_WINDOW )); then
        rm -f "$CIRCUIT_FILE" "$RESTART_COUNT_FILE"
    else
        echo "CIRCUIT OPEN: Kroki pod failed to stabilize after $MAX_RESTARTS attempts. Rendering disabled."
        echo "To retry: rm $CIRCUIT_FILE" >&2
        exit 1
    fi
fi

check_health() {
    curl -sf -m "$HEALTH_TIMEOUT" "$KROKI_ENDPOINT" >/dev/null 2>&1
}

start_pod() {
    echo "Starting Kroki pod..."
    # If pod exists but is not running (e.g. Created/Exited), tear it down first
    # so kroki.sh up (which refuses to run if pod exists) can succeed.
    if podman pod exists kroki 2>/dev/null && ! podman pod ps --filter name=kroki --format '{{.Status}}' 2>/dev/null | grep -qi running; then
        "$KROKI_SH" down 2>&1 || true
    fi
    "$KROKI_SH" up 2>&1 || true
    local i=0
    while (( i < STARTUP_POLL_MAX )); do
        if check_health; then
            echo "Kroki pod is healthy."
            # Reset restart counter on success
            rm -f "$RESTART_COUNT_FILE"
            return 0
        fi
        sleep "$STARTUP_POLL_INTERVAL"
        (( i++ ))
    done
    echo "Kroki pod failed to become healthy after $((STARTUP_POLL_MAX * STARTUP_POLL_INTERVAL))s." >&2
    return 1
}

restart_pod() {
    echo "Restarting Kroki pod..."
    "$KROKI_SH" down 2>&1 || true
    sleep 1
    start_pod
}

increment_restart_count() {
    local count=0
    if [[ -f "$RESTART_COUNT_FILE" ]]; then
        count=$(cat "$RESTART_COUNT_FILE" 2>/dev/null || echo 0)
    fi
    (( count++ ))
    echo "$count" > "$RESTART_COUNT_FILE"
    if (( count >= MAX_RESTARTS )); then
        echo "Circuit breaker tripped: $count restart attempts failed."
        date +%s > "$CIRCUIT_FILE"
        # Check for OOM kill
        local gateway_exit
        gateway_exit=$(podman inspect kroki-gateway --format '{{.State.ExitCode}}' 2>/dev/null || echo "unknown")
        if [[ "$gateway_exit" == "137" ]]; then
            echo "OOM DETECTED: Container was killed due to memory pressure."
            echo "Free RAM: $(free -h | awk '/^Mem:/{print $4}')"
            echo "Consider stopping unused containers."
        fi
        exit 1
    fi
}

# Main flow
if check_health; then
    exit 0
fi

# Pod not healthy — is it running at all?
if podman pod exists kroki 2>/dev/null && podman pod ps --filter name=kroki --format '{{.Status}}' 2>/dev/null | grep -qi running; then
    # Running but unhealthy — try restart
    increment_restart_count
    if restart_pod; then
        exit 0
    fi
    increment_restart_count
    restart_pod || exit 1
else
    # Not running — start it
    if start_pod; then
        exit 0
    fi
    # Start failed — count as restart attempt
    increment_restart_count
    if start_pod; then
        exit 0
    fi
    increment_restart_count
    start_pod || exit 1
fi
