#!/usr/bin/env bash
# install.sh — Unified kroki plugin installer. Idempotent.
#
# Usage:
#   install.sh [--vault-root PATH] [--rules-file PATH] [--state-dir PATH]
#              [--skip-systemd] [--skip-smoke]
#
# Steps:
#   1. Install kroki-theme.css into <vault-root>/.obsidian/snippets/
#   2. Append kroki extension block to <rules-file> inside Extension-point section (if missing)
#   3. Create <state-dir> (default ~/.kroki-plugin)
#   4. Install systemd user timers (skip if --skip-systemd or no systemctl)
#   5. Run smoke test (skip if --skip-smoke)
#   6. Print post-install checklist
#
# Exit codes:
#   0 — install complete (or already installed)
#   1 — vault/rules file missing, or smoke test failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VAULT_ROOT="$HOME/Documents/Obsidian Vault"
RULES_FILE="$HOME/.claude/rules/session-continuity.md"
STATE_DIR="$HOME/.kroki-plugin"
SKIP_SYSTEMD=false
SKIP_SMOKE=false
DO_UNINSTALL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --vault-root)   VAULT_ROOT="$2"; shift 2 ;;
        --rules-file)   RULES_FILE="$2"; shift 2 ;;
        --state-dir)    STATE_DIR="$2"; shift 2 ;;
        --skip-systemd) SKIP_SYSTEMD=true; shift ;;
        --skip-smoke)   SKIP_SMOKE=true; shift ;;
        --uninstall)    DO_UNINSTALL=true; shift ;;
        --help|-h)      sed -n '2,20p' "$0"; exit 0 ;;
        *)              echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

# --uninstall flag: remove kroki-session INSTALLER block, exit.
if $DO_UNINSTALL; then
    NEW_MARKER_OPEN='<!-- INSTALLER: kroki-session -->'
    NEW_MARKER_CLOSE='<!-- /INSTALLER: kroki-session -->'

    echo "uninstall kroki-session from session-continuity.md"
    echo "===================================================="

    if [[ ! -f "$RULES_FILE" ]]; then
        echo "  [skip] $RULES_FILE does not exist — nothing to uninstall"
        exit 0
    fi

    if grep -qF "$NEW_MARKER_OPEN" "$RULES_FILE"; then
        sed -i "\|$NEW_MARKER_OPEN|,\|$NEW_MARKER_CLOSE|d" "$RULES_FILE"
        echo "  [ok]   removed kroki-session INSTALLER block"
    else
        echo "  [skip] kroki-session INSTALLER block not present"
    fi

    echo ""
    echo "Note: '## diagrams' row in session-log-schema.md is NOT removed"
    echo "      (persistent schema extension — see Plan 5a §5.4)."
    echo "Note: state dir ~/.kroki-plugin/ is NOT removed."
    echo "Note: plugin files are NOT removed."
    exit 0
fi

[[ -d "$VAULT_ROOT" ]] || { echo "Error: vault root missing: $VAULT_ROOT" >&2; exit 1; }
[[ -f "$RULES_FILE" ]] || { echo "Error: rules file missing: $RULES_FILE" >&2; exit 1; }

echo "kroki installer"
echo "==============="
echo "  vault : $VAULT_ROOT"
echo "  rules : $RULES_FILE"
echo "  state : $STATE_DIR"
echo ""

# Step 1 — CSS snippet.
echo "[1/5] Install CSS snippet..."
"$SCRIPT_DIR/install-vault-theme.sh" "$VAULT_ROOT"

# Step 2 — session-continuity.md extension-point append with v0.9.0 migration.
OLD_MARKER_OPEN='<!-- INSTALLER: kroki -->'
OLD_MARKER_CLOSE='<!-- /INSTALLER: kroki -->'
NEW_MARKER_OPEN='<!-- INSTALLER: kroki-session -->'
NEW_MARKER_CLOSE='<!-- /INSTALLER: kroki-session -->'
EXTENSION_SECTION='## Extension point: installer-appended instructions'

INSTRUCTION_BLOCK=$(cat <<'BLOCK_EOF'

<!-- INSTALLER: kroki-session -->
## Kroki session bookends

If the current session involves a project with a `diagrams/` directory in its vault folder:

**At session start** (after reading memory per §"At the start of every session"):
Invoke `~/kroki-claude-plugin/scripts/session-start.sh --auto --project <project>`. Use the returned JSON payload (on stdout) to surface prior diagram inventory to the user.

**At session end** (after steps 1–4 of end-of-session sequence, before generating the resume prompt):
Invoke `~/kroki-claude-plugin/scripts/session-end.sh --auto --project <project>`. If a `v*` semver tag was placed on HEAD during this session and no milestone snapshot exists, auto-capture it. If the user named a milestone explicitly during the session (e.g., "snapshot as release-alpha"), pass `--milestone-label <label>` instead — and omit `--auto` so it is treated as an explicit invocation. Report the summary payload (stderr) in the session's close-out.

For multi-project sessions: run mode=end once per project touched, serially.

**Auto-invoke suppression:** both start and end auto-invocations respect `KROKI_SESSION_AUTO=0` — when the environment variable is set, the `--auto`-flagged invocations exit silently. Explicit user-triggered invocations (without `--auto`) run regardless of the env var.
<!-- /INSTALLER: kroki-session -->
BLOCK_EOF
)

echo ""
echo "[2/5] Patch session-continuity.md (extension-point contract)..."

# Preflight: session-continuity.md must have the Extension-point section
if ! grep -qF "$EXTENSION_SECTION" "$RULES_FILE"; then
    echo "Error: $RULES_FILE lacks the Extension point section." >&2
    echo "Upgrade session-continuity.md to Knowledge-Architecture v1 schema." >&2
    echo "See: ~/Documents/Obsidian Vault/Knowledge-Architecture/specs/2026-04-18-knowledge-architecture-design.md §6" >&2
    exit 1
fi

# Idempotency + migration:
# - If new marker present → no-op.
# - Else if old marker present → migrate (delete old block, append new).
# - Else → append fresh.
if grep -qF "$NEW_MARKER_OPEN" "$RULES_FILE"; then
    echo "  already migrated — skipping"
elif grep -qF "$OLD_MARKER_OPEN" "$RULES_FILE"; then
    # Delete old block via sed, then append new
    sed -i "\|$OLD_MARKER_OPEN|,\|$OLD_MARKER_CLOSE|d" "$RULES_FILE"
    printf '%s\n' "$INSTRUCTION_BLOCK" >> "$RULES_FILE"
    echo "  migrated kroki → kroki-session block"
else
    printf '%s\n' "$INSTRUCTION_BLOCK" >> "$RULES_FILE"
    echo "  appended kroki-session block"
fi

# Step 3 — state dir.
echo ""
echo "[3/5] Create state dir..."
mkdir -p "$STATE_DIR" "$STATE_DIR/a11y-reports"
echo "  ready: $STATE_DIR"

# Step 4 — systemd timers.
echo ""
echo "[4/5] systemd user timers..."
if $SKIP_SYSTEMD; then
    echo "  skipped (--skip-systemd)"
elif ! command -v systemctl >/dev/null 2>&1; then
    echo "  skipped (systemctl not available)"
else
    UNIT_DIR="$HOME/.config/systemd/user"
    mkdir -p "$UNIT_DIR"
    cat > "$UNIT_DIR/kroki-watchdog.service" <<SVCEOF
[Unit]
Description=Kroki container idle watchdog

[Service]
Type=oneshot
ExecStart=$SCRIPT_DIR/container-watchdog.sh
SVCEOF
    cat > "$UNIT_DIR/kroki-watchdog.timer" <<TMREOF
[Unit]
Description=Run kroki-watchdog every 15 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
TMREOF
    # Only enable if the watchdog script exists (Plan 5 adds it).
    if [[ -x "$SCRIPT_DIR/container-watchdog.sh" ]]; then
        systemctl --user daemon-reload
        systemctl --user enable --now kroki-watchdog.timer
        echo "  enabled kroki-watchdog.timer"
    else
        echo "  units written, not enabled (container-watchdog.sh not present yet)"
    fi
fi

# Step 4b (NEW — Plan 5b): version-check systemd units.
echo ""
echo "[4b/5] kroki-version-check systemd units..."
if $SKIP_SYSTEMD; then
    echo "  skipped (--skip-systemd)"
elif ! command -v systemctl >/dev/null 2>&1; then
    echo "  skipped (systemctl not available)"
else
    UNIT_DIR="$HOME/.config/systemd/user"
    mkdir -p "$UNIT_DIR"

    cat > "$UNIT_DIR/kroki-version-check.service" <<SVCEOF
[Unit]
Description=Kroki daily version check

[Service]
Type=oneshot
ExecStart=$SCRIPT_DIR/version-check.sh
SVCEOF

    cat > "$UNIT_DIR/kroki-version-check.timer" <<TMREOF
[Unit]
Description=Run kroki-version-check daily

[Timer]
OnBootSec=5min
OnUnitActiveSec=1d
Persistent=true

[Install]
WantedBy=timers.target
TMREOF

    systemctl --user daemon-reload

    # Enable version-check.timer. (kroki-watchdog.timer is enabled in step 4.)
    if [[ -x "$SCRIPT_DIR/version-check.sh" ]]; then
        systemctl --user enable --now kroki-version-check.timer
        echo "  enabled kroki-version-check.timer"
    fi
fi

# Step 4c (NEW — Plan 5b): enable linger so user timers run logged-out.
echo ""
echo "[4c/5] enable-linger..."
if ! command -v loginctl >/dev/null 2>&1; then
    echo "  skipped (loginctl not available)"
elif [[ "$(loginctl show-user "$USER" --property=Linger --value 2>/dev/null)" != "yes" ]]; then
    if loginctl enable-linger "$USER" 2>/dev/null; then
        echo "  linger enabled for $USER"
    else
        echo "  WARNING: enable-linger failed (may require interactive auth). Timers will only run during login sessions."
    fi
else
    echo "  linger already enabled"
fi

# Step 4d (NEW — Plan 5b): install ~/.local/bin CLI symlinks.
echo ""
echo "[4d/5] CLI symlinks in ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
ln -sf "$SCRIPT_DIR/container-watchdog.sh" "$HOME/.local/bin/kroki-watchdog"
ln -sf "$SCRIPT_DIR/version-check.sh"     "$HOME/.local/bin/kroki-version-check"
ln -sf "$SCRIPT_DIR/upgrade.sh"           "$HOME/.local/bin/kroki-upgrade"
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"; then
    echo "  NOTE: \$HOME/.local/bin is not in \$PATH. Add it to ~/.bashrc or ~/.zshrc."
fi

# Step 5 — smoke test.
echo ""
echo "[5/5] smoke test..."
if $SKIP_SMOKE; then
    echo "  skipped (--skip-smoke)"
elif [[ -x "$REPO_ROOT/tests/smoke.sh" ]]; then
    if "$REPO_ROOT/tests/smoke.sh" >/dev/null 2>&1; then
        echo "  PASS (quick mode)"
    else
        echo "  FAIL — see 'tests/smoke.sh' output" >&2
        exit 1
    fi
fi

echo ""
echo "Install complete."
echo ""
echo "Next step: open Obsidian -> Settings -> Appearance -> CSS snippets,"
echo "and toggle 'kroki-theme' on."
