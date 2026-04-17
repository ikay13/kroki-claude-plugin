#!/usr/bin/env bash
# a11y-check.sh — Advisory accessibility validator for rendered SVGs.
#
# Usage:
#   a11y-check.sh <svg-file>
#
# Checks:
#   - WCAG AA contrast (stroke vs background)
#   - Palette adherence (non-Okabe-Ito hex codes)
#   - Grayscale distinguishability (pairs with similar luminance)
#   - Colorblind simulation (deuteranopia + protanopia)
#
# Always exits 0 when the input is readable (advisory, non-blocking).
# Exit 2 on usage error / missing file.
#
# Writes report to $KROKI_STATE_DIR/a11y-reports/<basename>.log
# (default $KROKI_STATE_DIR=$HOME/.kroki-plugin).

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: a11y-check.sh <svg-file>" >&2
    exit 2
fi

SVG="$1"
if [[ ! -f "$SVG" ]]; then
    echo "Error: SVG not found: $SVG" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATE_DIR="${KROKI_STATE_DIR:-$HOME/.kroki-plugin}"
REPORT_DIR="$STATE_DIR/a11y-reports"
BASE="$(basename "$SVG" .svg)"
REPORT="$REPORT_DIR/${BASE}.log"

mkdir -p "$REPORT_DIR"

export KROKI_REPO_ROOT="$REPO_ROOT"
set +e
python3 - "$SVG" "$REPORT" <<'PYEOF'
import os
import sys
from pathlib import Path

repo = os.environ.get("KROKI_REPO_ROOT")
if repo:
    sys.path.insert(0, repo)

from lib.kroki_util import (  # noqa: E402
    OKABE_ITO_PALETTE,
    extract_hex_colors,
    palette_violations,
    grayscale_collisions,
    colorblind_sim,
    contrast_ratio,
)

svg_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
svg = svg_path.read_text()
colors = sorted(extract_hex_colors(svg))
violations = palette_violations(svg, OKABE_ITO_PALETTE)
collisions = grayscale_collisions(colors)

bg_light = "#F7F7F7"
contrast_warnings = [
    (c, bg_light, round(contrast_ratio(c, bg_light), 2))
    for c in colors
    if c.upper() != bg_light.upper() and contrast_ratio(c, bg_light) < 4.5
]

cb_shifts_d = {c: colorblind_sim(c, "deuteranopia") for c in colors}
cb_shifts_p = {c: colorblind_sim(c, "protanopia") for c in colors}

lines = [f"# a11y report for {svg_path.name}"]
lines.append(f"colors: {colors}")
lines.append(f"palette_violations: {violations}")
lines.append(f"grayscale_collisions: {collisions}")
lines.append(f"low_contrast_vs_bg_light: {contrast_warnings}")
lines.append(f"deuteranopia_shifts: {cb_shifts_d}")
lines.append(f"protanopia_shifts: {cb_shifts_p}")
report_path.write_text("\n".join(lines) + "\n")

if violations:
    print(f"a11y: palette violations in {svg_path.name}: {violations}", file=sys.stderr)
if collisions:
    print(f"a11y: grayscale collisions in {svg_path.name}: {collisions}", file=sys.stderr)
if contrast_warnings:
    print(f"a11y: low contrast in {svg_path.name}: {contrast_warnings}", file=sys.stderr)
PYEOF
py_rc=$?
set -e
# Python failure does NOT break advisory — warnings already on stderr.
# Log a hint if python crashed; always exit 0.
if (( py_rc != 0 )); then
    echo "a11y: internal error ($py_rc) — report may be incomplete for $(basename "$SVG")" >&2
fi

exit 0
