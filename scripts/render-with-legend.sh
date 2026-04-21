#!/usr/bin/env bash
# render-with-legend.sh — Render with appended legend (stitch mode).
#
# Usage:
#   render-with-legend.sh <source> [--type <type>] [--out <dir>]
#                                   [--placement top-right|below|...]
#                                   [--palette <name>]
#
# For languages without native legend syntax (mermaid, ditaa, erd, ...),
# this composes a legend-SVG from styles/*.yml and stitches it below the
# base render using kroki_util.stitch_svgs_vertical.
#
# Emits <name>.light.svg and <name>.dark.svg.
#
# Does NOT emit the Obsidian <div class="kroki-dual"> wrapper — that's
# embed-in-md.sh's job, and the blank-line rule from b33d1af lives there.
#
# Exit codes:
#   0 — success
#   1 — pod unhealthy
#   2 — render failed
#   3 — usage error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RENDER="$SCRIPT_DIR/render.sh"
STYLES_DIR="$REPO_ROOT/styles"

usage() {
    cat >&2 <<EOF
Usage: render-with-legend.sh <source> [--type <type>] [--out <dir>]
                                      [--placement <mode>] [--palette <name>]
EOF
    exit 3
}

SOURCE=""
DIAGRAM_TYPE=""
OUTPUT_DIR=""
PLACEMENT="below"
PALETTE="okabe_ito"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)      DIAGRAM_TYPE="$2"; shift 2 ;;
        --out)       OUTPUT_DIR="$2"; shift 2 ;;
        --placement) PLACEMENT="$2"; shift 2 ;;
        --palette)   PALETTE="$2"; shift 2 ;;
        --help|-h)   usage ;;
        -*)          echo "Unknown option: $1" >&2; usage ;;
        *)           SOURCE="$1"; shift ;;
    esac
done

[[ -z "$SOURCE" ]] && usage
[[ ! -f "$SOURCE" ]] && { echo "Error: source missing: $SOURCE" >&2; exit 3; }

# --- Plan 5c editor lock gate ---
# Short-circuit when no lock file present (zero subprocess overhead on common path).
# Note: render.sh also has this gate. When render-with-legend.sh calls render.sh internally,
# the gate will fire a second time there. This is the known "double-fire" limitation
# documented in the design doc (§8 Known limitations). Double-fire is benign.
if [[ -f "$HOME/.kroki-plugin/.active-editor.lock" ]]; then
    PLUGIN_ROOT_FOR_GATE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    # Canonicalize SOURCE to absolute path BEFORE the subshell — otherwise a
    # relative path would resolve against PLUGIN_ROOT_FOR_GATE (subshell cwd)
    # instead of the caller's cwd, causing a fail-open mismatch against the
    # lock's realpath'd source_path.
    SOURCE_ABS_FOR_GATE="$(realpath "$SOURCE")"
    gate_rc=0
    (cd "$PLUGIN_ROOT_FOR_GATE" && python3 -m lib.kroki_session.lock check --source "$SOURCE_ABS_FOR_GATE") || gate_rc=$?
    case $gate_rc in
        0) : ;;  # ok / locked-other-file / blank-session — proceed.
        2)
            echo "render-with-legend.sh: editor lock active on $SOURCE. Run scripts/editor-close.sh to release." >&2
            exit 2
            ;;
        *)
            echo "render-with-legend.sh: lock check failed unexpectedly (exit $gate_rc)." >&2
            echo "Aborting to protect possible in-flight edits (fail-closed)." >&2
            echo "To force-unblock: mv \"$HOME/.kroki-plugin/.active-editor.lock\" ~/.local/share/Trash/files/ and retry." >&2
            exit 2
            ;;
    esac
fi
# --- end Plan 5c editor lock gate ---

BASE="$(basename "$SOURCE")"
NAME="${BASE%.*}"
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
fi

# Step 1 — render base dual-SVGs via render.sh.
RENDER_ARGS=("$SOURCE" "--out" "$OUTPUT_DIR" "--mode" "dual")
[[ -n "$DIAGRAM_TYPE" ]] && RENDER_ARGS+=("--type" "$DIAGRAM_TYPE")
"$RENDER" "${RENDER_ARGS[@]}" >/dev/null

LIGHT="$OUTPUT_DIR/${NAME}.light.svg"
DARK="$OUTPUT_DIR/${NAME}.dark.svg"

for v in "$LIGHT" "$DARK"; do
    [[ -s "$v" ]] || { echo "Error: render produced no $v" >&2; exit 2; }
done

# Step 2 — compose legend + stitch below. Python uses kroki_util helpers.
export KROKI_REPO_ROOT="$REPO_ROOT"
python3 - "$LIGHT" "$DARK" "$STYLES_DIR" "$PALETTE" "$PLACEMENT" <<'PYEOF'
import os
import sys
from pathlib import Path

repo = os.environ.get("KROKI_REPO_ROOT")
if repo:
    sys.path.insert(0, repo)

import yaml
from lib.kroki_util import (  # noqa: E402
    atomic_write, build_legend_svg, stitch_svgs_vertical, dark_remap,
)

light_path = Path(sys.argv[1])
dark_path = Path(sys.argv[2])
styles_dir = Path(sys.argv[3])
palette_name = sys.argv[4]
# placement arg reserved — v1 always stitches below.

# Load palette: base + optional named override.
palette_yaml = yaml.safe_load((styles_dir / "palette.yml").read_text())
palette = dict(palette_yaml["okabe_ito"])

override_path = styles_dir / "palettes" / f"{palette_name}.yml"
if palette_name != "okabe_ito" and override_path.exists():
    overrides = yaml.safe_load(override_path.read_text()).get("overrides", {})
    palette.update(overrides)

# Build a legend SVG based on the light variant's color content.
light_svg = light_path.read_text()
legend_svg = build_legend_svg(light_svg, palette)

# Skip legend stitch if empty (no palette colors used).
if 'viewBox="0 0 1 1"' in legend_svg:
    sys.exit(0)

# Stitch legend below the base for both variants.
stitched_light = stitch_svgs_vertical([light_svg, legend_svg])
stitched_dark = stitch_svgs_vertical(
    [dark_path.read_text(), dark_remap(legend_svg)]
)
atomic_write(light_path, stitched_light)
atomic_write(dark_path, stitched_dark)
PYEOF

exit 0
