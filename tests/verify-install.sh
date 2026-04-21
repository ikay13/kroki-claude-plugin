#!/usr/bin/env bash
# verify-install.sh — Confirm kroki plugin is installed and configured.
#
# Usage:
#   verify-install.sh [--vault-root PATH] [--rules-file PATH] [--state-dir PATH]
#                     [--skip-systemd] [--skip-pod] [--skip-smoke]
#
# 18 checks (per design spec §14 + Plan 5b):
#   [1] CSS snippet exists in vault
#   [2] session-continuity.md has kroki-session extension-point marker block (new)
#   [3] state dir exists
#   [4] pod starts (skippable)
#   [5] systemd timer loaded (skippable)
#   [6] smoke test passes (skippable)
#   [7] repo scripts are executable
#   [8] old v0.9.0 kroki marker absent (migration completed)
#   [9] session-log-schema.md has ## diagrams row
#   [10] kroki-session bash entrypoints executable
#   [11] editor-lock scripts executable
#   [12] lib.kroki_session.lock imports cleanly
#   [13] SKILL.md references .active-editor.lock
#   [14] kroki-watchdog.timer is active (Plan 5b)
#   [15] kroki-version-check.timer is active (Plan 5b)
#   [16] linger enabled for $USER (Plan 5b)
#   [17] lib.kroki_container is importable (Plan 5b)
#   [18] ~/.local/bin CLI symlinks resolve and are executable (Plan 5b)
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

# [2] session-continuity.md kroki-session extension-point marker (new).
if grep -qF '<!-- INSTALLER: kroki-session -->' "$RULES_FILE" 2>/dev/null; then
    check "session-continuity.md kroki-session marker present" ok
else
    check "session-continuity.md kroki-session marker present" "no <!-- INSTALLER: kroki-session --> marker in $RULES_FILE"
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

# [8] old v0.9.0 marker absent (migration completed).
if grep -qF '<!-- INSTALLER: kroki -->' "$RULES_FILE" 2>/dev/null; then
    check "old v0.9.0 marker absent (migration completed)" "<!-- INSTALLER: kroki --> still present in $RULES_FILE — migration failed"
else
    check "old v0.9.0 marker absent (migration completed)" ok
fi

# [9] session-log-schema.md has ## diagrams row.
SCHEMA_FILE="${SCHEMA_FILE:-$HOME/.claude/rules/session-log-schema.md}"
if grep -qE '^\| `## diagrams`' "$SCHEMA_FILE" 2>/dev/null; then
    check "session-log-schema.md has ## diagrams row" ok
else
    check "session-log-schema.md has ## diagrams row" "no ## diagrams row in $SCHEMA_FILE"
fi

# [10] kroki-session bash entrypoints executable.
ENTRYPOINTS_OK=true
for s in "$REPO_ROOT"/scripts/session-start.sh \
         "$REPO_ROOT"/scripts/session-end.sh \
         "$REPO_ROOT"/scripts/session-snapshot.sh; do
    [[ -x "$s" ]] || ENTRYPOINTS_OK=false
done
if $ENTRYPOINTS_OK; then
    check "kroki-session entrypoints executable" ok
else
    check "kroki-session entrypoints executable" "one of session-{start,end,snapshot}.sh not executable"
fi

# [11] editor-lock scripts (Plan 5c) executable.
EDITOR_SCRIPTS_OK=true
for s in "$REPO_ROOT"/scripts/editor-open.sh \
         "$REPO_ROOT"/scripts/editor-close.sh; do
    [[ -x "$s" ]] || EDITOR_SCRIPTS_OK=false
done
if $EDITOR_SCRIPTS_OK; then
    check "editor-open.sh and editor-close.sh executable" ok
else
    check "editor-open.sh and editor-close.sh executable" "one of editor-{open,close}.sh missing or not executable"
fi

# [12] lock module importable.
if (cd "$REPO_ROOT" && python3 -c "from lib.kroki_session import lock" 2>/dev/null); then
    check "lib.kroki_session.lock imports cleanly" ok
else
    check "lib.kroki_session.lock imports cleanly" "import failed — broken plugin install"
fi

# [13] SKILL.md references the editor lock file.
if grep -qF '.active-editor.lock' "$REPO_ROOT/skills/kroki/SKILL.md" 2>/dev/null; then
    check "skills/kroki/SKILL.md references .active-editor.lock" ok
else
    check "skills/kroki/SKILL.md references .active-editor.lock" "no .active-editor.lock reference in SKILL.md"
fi

# --- Plan 5b checks ---------------------------------------------------------

# [14] kroki-watchdog.timer is active.
if $SKIP_SYSTEMD; then
    echo "  [skip] kroki-watchdog.timer is active (--skip-systemd)"
elif ! command -v systemctl >/dev/null 2>&1; then
    echo "  [skip] kroki-watchdog.timer is active (systemctl unavailable)"
elif systemctl --user is-active --quiet kroki-watchdog.timer 2>/dev/null; then
    check "kroki-watchdog.timer is active" ok
else
    check "kroki-watchdog.timer is active" "timer not active or not loaded"
fi

# [15] kroki-version-check.timer is active.
if $SKIP_SYSTEMD; then
    echo "  [skip] kroki-version-check.timer is active (--skip-systemd)"
elif ! command -v systemctl >/dev/null 2>&1; then
    echo "  [skip] kroki-version-check.timer is active (systemctl unavailable)"
elif systemctl --user is-active --quiet kroki-version-check.timer 2>/dev/null; then
    check "kroki-version-check.timer is active" ok
else
    check "kroki-version-check.timer is active" "timer not active or not loaded"
fi

# [16] linger enabled for $USER.
if ! command -v loginctl >/dev/null 2>&1; then
    echo "  [skip] linger enabled for \$USER (loginctl unavailable)"
elif [[ "$(loginctl show-user "$USER" --property=Linger --value 2>/dev/null)" == "yes" ]]; then
    check "linger enabled for \$USER" ok
else
    check "linger enabled for \$USER" "loginctl show-user returned no or missing"
fi

# [17] lib.kroki_container is importable.
if (cd "$REPO_ROOT" && PYTHONPATH=. python3 -c "from lib.kroki_container import watchdog, version_check, upgrade, common" 2>/dev/null); then
    check "lib.kroki_container is importable" ok
else
    check "lib.kroki_container is importable" "import failed — check lib/kroki_container/ structure"
fi

# [18] ~/.local/bin CLI symlinks resolve and are executable.
CLI_SYMLINKS_OK=true
for bin in "$HOME/.local/bin/kroki-watchdog" \
           "$HOME/.local/bin/kroki-version-check" \
           "$HOME/.local/bin/kroki-upgrade"; do
    if [[ ! -x "$bin" ]]; then
        CLI_SYMLINKS_OK=false
        break
    fi
done
if $CLI_SYMLINKS_OK; then
    check "~/.local/bin CLI symlinks resolve and are executable" ok
else
    check "~/.local/bin CLI symlinks resolve and are executable" "one or more symlinks missing or not executable"
fi

echo ""
echo "Results: $pass ok, $fail fail"
(( fail == 0 ))
