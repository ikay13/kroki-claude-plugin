#!/usr/bin/env bash
# upgrade.sh — Kroki container upgrade with rollback-on-regression.
# User-invoked; NOT a systemd ExecStart target.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PLUGIN_ROOT"

STATE_DIR="${KROKI_STATE_DIR:-$HOME/.kroki-plugin}"
KROKI_SH="${KROKI_SH:-$HOME/kroki/kroki.sh}"
POD_NAME="${KROKI_POD:-kroki}"
DRY_RUN=0

# --- parse args --------------------------------------------------------------

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help)
            cat <<'HELP'
usage: upgrade.sh [--dry-run]

  (no args)   Full upgrade: baseline → tag :last-good → pull → restart →
              smoke → pytest → commit or rollback.
  --dry-run   Show what would happen; no tagging, no pulls, no restart.
HELP
            exit 0 ;;
    esac
done

LOG_FILE="$STATE_DIR/upgrade-$(date -u +%Y-%m-%dT%H%M%S).log"
mkdir -p "$STATE_DIR"
: > "$LOG_FILE"
echo "upgrade log: $LOG_FILE"

# Tee stdout + stderr to the forensic log while keeping terminal output.
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== upgrade.sh — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[MODE] dry-run"
else
    echo "[MODE] full upgrade"
fi

# --- Step 1: PRE-FLIGHT -------------------------------------------------------

echo
echo "--- Step 1: pre-flight ---"

# Editor-lock check
if python3 -c "
import sys
try:
    from lib.kroki_session.lock import read_lock, is_stale
    l = read_lock()
    sys.exit(0 if (l and not is_stale(l)) else 1)
except Exception as e:
    sys.stderr.write(f'lock check error: {e}\n')
    sys.exit(2)
"; then
    echo "ERROR: Active editor lock held." >&2
    echo "Upgrade requires pod restart, which would break your editor session." >&2
    echo "Close the editor first:" >&2
    echo "  $PLUGIN_ROOT/scripts/editor-close.sh" >&2
    exit 1
fi

# Circuit breaker
if [[ -f "$STATE_DIR/.pod-circuit-open" ]]; then
    echo "ERROR: Circuit breaker open ($STATE_DIR/.pod-circuit-open)." >&2
    echo "Investigate prior failure first, then: rm $STATE_DIR/.pod-circuit-open" >&2
    exit 1
fi

# Network
if ! python3 -c "
from lib.kroki_container import common
import sys
sys.exit(0 if common.network_available() else 1)
"; then
    echo "ERROR: No network connectivity. Cannot pull upstream images." >&2
    exit 1
fi

# Pod health
if ! "$PLUGIN_ROOT/scripts/pod-health.sh" >/dev/null; then
    echo "ERROR: pod-health.sh failed. Not touching pod state." >&2
    exit 1
fi

# ALL pre-flight checks passed. Write .upgrade-in-progress.
if [[ "$DRY_RUN" -eq 0 ]]; then
    echo "$$ $(date +%s)" > "$STATE_DIR/.upgrade-in-progress"
fi

echo "pre-flight OK"

# --- Step 2: BASELINE CAPTURE (skipped on --dry-run) -------------------------

if [[ "$DRY_RUN" -eq 0 ]]; then
    echo
    echo "--- Step 2: baseline smoke capture ---"
    BASELINE_TMP="$(mktemp)"
    if "$PLUGIN_ROOT/tests/smoke.sh" --full > "$BASELINE_TMP" 2>&1; then
        BASELINE_RC=0
    else
        BASELINE_RC=$?
    fi
    python3 - "$BASELINE_TMP" <<'PYEOF'
import json
import re
import sys
from pathlib import Path
from lib.kroki_container import common

text = Path(sys.argv[1]).read_text()
# Parse smoke output: expect "PASS: <name>" / "FAIL: <name>" lines
result = {}
for m in re.finditer(r'^(PASS|FAIL):\s*(\S+)', text, re.M):
    verdict, fixture = m.group(1).lower(), m.group(2)
    result[fixture] = verdict
common.write_state(".upgrade-last-smoke.json", {
    "captured_at": __import__("time").time(),
    "pre_upgrade_fixtures": result,
})
total = len(result)
passed = sum(1 for v in result.values() if v == "pass")
print(f"baseline: {passed}/{total} passing", file=sys.stderr)
PYEOF
    rm -f "$BASELINE_TMP"
    echo "baseline captured → $STATE_DIR/.upgrade-last-smoke.json"
fi

# --- Step 3: IMAGE DISCOVERY -------------------------------------------------

echo
echo "--- Step 3: image discovery ---"

DISCOVERY_JSON="$(python3 -c "
import json
from lib.kroki_container import version_check, upgrade
pod_images = version_check.discover_pod_images('$POD_NAME')
upstream = [ref for ref in pod_images if upgrade.is_upstream(ref)]
local = [ref for ref in pod_images if not upgrade.is_upstream(ref)]
print(json.dumps({
    'all': pod_images,
    'upstream': upstream,
    'local_skipped': local,
}))
")"

echo "$DISCOVERY_JSON" | python3 -m json.tool

# Write .last-good-mapping.json (list of upstream images to tag+restore)
if [[ "$DRY_RUN" -eq 0 ]]; then
    python3 -c "
import json
from lib.kroki_container import common
d = json.loads('''$DISCOVERY_JSON''')
mapping = {ref: f'{ref.rsplit(\":\", 1)[0]}:last-good' for ref in d['upstream']}
common.write_state('.last-good-mapping.json', mapping)
print(f'wrote .last-good-mapping.json with {len(mapping)} entries')
"
fi

# On --dry-run: print plan and exit cleanly.
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo
    echo "--- DRY-RUN complete — no state mutations performed ---"
    echo "Upstream images that would be tagged :last-good and pulled:"
    echo "$DISCOVERY_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for ref in d['upstream']:
    print(f'  {ref}')
"
    echo "Locally-built images (skipped during upgrade):"
    echo "$DISCOVERY_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for ref in d['local_skipped']:
    print(f'  {ref}')
"
    exit 0
fi

# --- rollback helper (used by trap + triggers A/B/C) ------------------------

_rollback_from_last_good() {
    echo
    echo "!!! ROLLBACK — reverting :last-good tags !!!"
    "$KROKI_SH" down --force 2>/dev/null || true
    sleep 2
    # Retag :last-good → :latest for each image in .last-good-mapping.json
    python3 - <<'PYEOF'
import json
import subprocess
from lib.kroki_container import common

mapping = common.read_state(".last-good-mapping.json") or {}
for ref, lg in mapping.items():
    base = ref.rsplit(":", 1)[0]
    latest_tag = f"{base}:latest"
    print(f"  retag {lg} → {latest_tag}")
    subprocess.run(["podman", "tag", lg, latest_tag], check=False)
PYEOF
    "$KROKI_SH" up
    # Sanity re-run: if this also fails, trip circuit breaker
    if ! "$PLUGIN_ROOT/scripts/pod-health.sh" >/dev/null; then
        echo "$(date +%s)" > "$STATE_DIR/.pod-circuit-open"
        python3 -c "
from lib.kroki_container import common
common.notify_and_log('critical',
    'Kroki upgrade rolled back AND circuit tripped',
    'Rollback completed but pod still unhealthy. Manual investigation required. '
    'See forensic log: $LOG_FILE')
"
    fi
    rm -f "$STATE_DIR/.upgrade-in-progress"
}

# --- Step 4: TAG :last-good --------------------------------------------------

echo
echo "--- Step 4: tag :last-good on upstream images ---"

# Install trap for steps 4-8
trap '_rollback_from_last_good; exit 130' INT TERM

python3 - <<'PYEOF'
import json
import subprocess
from lib.kroki_container import common

mapping = common.read_state(".last-good-mapping.json") or {}
for ref, lg in mapping.items():
    print(f"  tag {ref} → {lg}")
    r = subprocess.run(["podman", "tag", ref, lg], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ERROR: podman tag failed for {ref}: {r.stderr}")
PYEOF

# --- Step 5: PULL NEW IMAGES -------------------------------------------------

echo
echo "--- Step 5: pull new images ---"

PULL_REPORT="$(python3 - <<'PYEOF'
import json
import subprocess
from lib.kroki_container import common, version_check

mapping = common.read_state(".last-good-mapping.json") or {}
pre = {ref: version_check.inspect_local_digest(ref) for ref in mapping}

changed_count = 0
for ref in mapping:
    print(f"  pull {ref}")
    r = subprocess.run(["podman", "pull", ref], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ERROR: podman pull failed for {ref}: {r.stderr}")

post = {ref: version_check.inspect_local_digest(ref) for ref in mapping}
changed_count = sum(1 for ref in mapping if pre[ref] != post[ref])
print(json.dumps({"changed_count": changed_count, "total": len(mapping)}))
PYEOF
)"

echo "$PULL_REPORT" | tail -1
CHANGED_COUNT=$(echo "$PULL_REPORT" | tail -1 | python3 -c "import json,sys; print(json.load(sys.stdin)['changed_count'])")

if [[ "$CHANGED_COUNT" == "0" ]]; then
    echo
    echo "Already current — no upstream changes detected."
    echo "Cleaning up :last-good tags (no rollback target needed this cycle)."
    trap - INT TERM
    rm -f "$STATE_DIR/.upgrade-in-progress"
    exit 0
fi

# --- Step 6: POD RESTART -----------------------------------------------------

echo
echo "--- Step 6: pod restart ---"

"$KROKI_SH" down || true
sleep 2

if ! "$KROKI_SH" up; then
    echo "pod failed to come up — TRIGGER A ROLLBACK"
    _rollback_from_last_good
    python3 -c "
from lib.kroki_container import common
common.notify_and_log('critical',
    'Kroki upgrade rolled back',
    'Trigger: pod health. Pod did not start after pull. Reverted to :last-good.',
    suggested_cmds=['cat $LOG_FILE'])
"
    trap - INT TERM
    exit 1
fi

# Poll pod-health.sh for up to 60s
if ! timeout 60 bash -c "
while ! '$PLUGIN_ROOT/scripts/pod-health.sh' >/dev/null 2>&1; do
    sleep 2
done
"; then
    echo "pod-health.sh never succeeded within 60s — TRIGGER A ROLLBACK"
    _rollback_from_last_good
    python3 -c "
from lib.kroki_container import common
common.notify_and_log('critical',
    'Kroki upgrade rolled back',
    'Trigger: pod health. Pod came up but stayed unhealthy. Reverted to :last-good.',
    suggested_cmds=['cat $LOG_FILE'])
"
    trap - INT TERM
    exit 1
fi

echo "pod healthy after restart"
