#!/usr/bin/env bash
# verify-install.sh — Confirm kroki plugin is installed and configured.
#
# Usage:
#   verify-install.sh [--vault-root PATH] [--rules-file PATH] [--state-dir PATH]
#                     [--skip-systemd] [--skip-pod] [--skip-smoke]
#
# 7 checks (per design spec §14):
#   [1] CSS snippet exists in vault
#   [2] session-continuity.md has step 5 (kroki-session reference)
#   [3] state dir exists
#   [4] pod starts (skippable)
#   [5] systemd timer loaded (skippable)
#   [6] smoke test passes (skippable)
#   [7] repo scripts are executable
#
# Exit codes:
#   0 — all checks passed
#   1 — at least one check failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VAULT_ROOT="$HOME/Documents/Obsidian Vault"
RULES_FILE="$HOME/.claude/rules/session-continuity.md"
STATE_DIR="$HOME/.kroki-plugin"
SKIP_SYSTEMD=false
SKIP_POD=false
SKIP_SMOKE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --vault-root)   VAULT_ROOT="$2"; shift 2 ;;
        --rules-file)   RULES_FILE="$2"; shift 2 ;;
        --state-dir)    STATE_DIR="$2"; shift 2 ;;
        --skip-systemd) SKIP_SYSTEMD=true; shift ;;
        --skip-pod)     SKIP_POD=true; shift ;;
        --skip-smoke)   SKIP_SMOKE=true; shift ;;
        *)              echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

pass=0
fail=0

check() {
    local label="$1"
    local status="$2"
    if [[ "$status" == "ok" ]]; then
        echo "  [OK]   $label"
        ((++pass))
    else
        echo "  [FAIL] $label — $status" >&2
        ((++fail))
    fi
}

echo "verify-install"
echo "=============="

# [1] CSS snippet.
if [[ -f "$VAULT_ROOT/.obsidian/snippets/kroki-theme.css" ]]; then
    check "CSS snippet installed" ok
else
    check "CSS snippet installed" "$VAULT_ROOT/.obsidian/snippets/kroki-theme.css missing"
fi

# [2] session-continuity.md step 5.
if grep -qF "kroki-session" "$RULES_FILE" 2>/dev/null; then
    check "session-continuity.md step 5 present" ok
else
    check "session-continuity.md step 5 present" "no kroki-session line in $RULES_FILE"
fi

# [3] state dir.
if [[ -d "$STATE_DIR" ]]; then
    check "state dir exists" ok
else
    check "state dir exists" "$STATE_DIR missing"
fi

# [4] pod starts.
if $SKIP_POD; then
    echo "  [skip] pod health (--skip-pod)"
elif "$REPO_ROOT/scripts/pod-health.sh" >/dev/null 2>&1; then
    check "pod healthy" ok
else
    check "pod healthy" "pod-health.sh returned non-zero"
fi

# [5] systemd timer.
if $SKIP_SYSTEMD; then
    echo "  [skip] systemd timer (--skip-systemd)"
elif ! command -v systemctl >/dev/null 2>&1; then
    echo "  [skip] systemd timer (systemctl unavailable)"
elif systemctl --user list-timers --all 2>/dev/null | grep -q kroki-watchdog; then
    check "kroki-watchdog.timer loaded" ok
else
    check "kroki-watchdog.timer loaded" "timer not in systemctl list"
fi

# [6] smoke test.
if $SKIP_SMOKE; then
    echo "  [skip] smoke test (--skip-smoke)"
elif "$REPO_ROOT/tests/smoke.sh" >/dev/null 2>&1; then
    check "smoke test passes" ok
else
    check "smoke test passes" "smoke.sh returned non-zero"
fi

# [7] scripts executable.
EXECUTABLES_OK=true
for s in "$REPO_ROOT"/scripts/*.sh; do
    [[ -x "$s" ]] || EXECUTABLES_OK=false
done
if $EXECUTABLES_OK; then
    check "all scripts executable" ok
else
    check "all scripts executable" "some scripts/*.sh missing +x"
fi

echo ""
echo "Results: $pass ok, $fail fail"
(( fail == 0 ))
