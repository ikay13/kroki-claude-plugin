#!/usr/bin/env bash
# render.sh — Render diagram source to SVG via Kroki CLI.
#
# Usage:
#   render.sh <source_file> [--type <type>] [--format <fmt>] [--out <dir>]
#                           [--mode dual|light|dark|single]
#
# Modes:
#   dual   (default) — emit <name>.light.svg and <name>.dark.svg
#   light            — emit <name>.light.svg only
#   dark             — emit <name>.dark.svg only
#   single           — emit <name>.svg (no suffix; Plan 1 backward-compat)
#
# Defaults:
#   --type:   inferred from file extension (see alias map below)
#   --format: svg
#   --out:    directory of source file
#   --mode:   dual
#
# Exit codes:
#   0 — render succeeded
#   1 — pod unhealthy
#   2 — render failed (syntax, timeout, empty output)
#   3 — usage error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KROKI_CLI="${KROKI_CLI:-$HOME/go/bin/kroki}"
STATE_DIR="${KROKI_STATE_DIR:-$HOME/.kroki-plugin}"
LAST_USE_FILE="$STATE_DIR/.last-use"
PY_UTIL="$REPO_ROOT/lib/kroki_util.py"

usage() {
    local code="${1:-3}"
    cat <<EOF
Usage: render.sh <source_file> [--type <type>] [--format <fmt>] [--out <dir>]
                               [--mode dual|light|dark|single]

Options:
  --type    Diagram type (plantuml, mermaid, graphviz, d2, ...).
            Default: inferred from file extension.
  --format  Output format (svg, png, pdf). Default: svg.
  --out     Output directory. Default: same as source file.
  --mode    Render mode. Default: dual.
              dual   -> <name>.light.svg + <name>.dark.svg
              light  -> <name>.light.svg
              dark   -> <name>.dark.svg
              single -> <name>.svg (Plan 1 backward-compat)
EOF
    exit "$code"
}

SOURCE=""
DIAGRAM_TYPE=""
OUTPUT_FORMAT="svg"
OUTPUT_DIR=""
MODE="dual"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)   DIAGRAM_TYPE="$2"; shift 2 ;;
        --format) OUTPUT_FORMAT="$2"; shift 2 ;;
        --out)    OUTPUT_DIR="$2"; shift 2 ;;
        --mode)   MODE="$2"; shift 2 ;;
        --help|-h) usage 0 ;;
        -*)       echo "Unknown option: $1" >&2; usage ;;
        *)        SOURCE="$1"; shift ;;
    esac
done

if [[ -z "$SOURCE" ]]; then
    echo "Error: source file required." >&2
    usage
fi
if [[ ! -f "$SOURCE" ]]; then
    echo "Error: source file not found: $SOURCE" >&2
    exit 3
fi

case "$MODE" in
    dual|light|dark|single) ;;
    *) echo "Error: invalid --mode '$MODE' (dual|light|dark|single)" >&2; exit 3 ;;
esac

SOURCE_BASE="$(basename "$SOURCE")"
SOURCE_NAME="${SOURCE_BASE%.*}"
SOURCE_DIR="$(cd "$(dirname "$SOURCE")" && pwd)"

if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="$SOURCE_DIR"
fi
mkdir -p "$OUTPUT_DIR"

"$SCRIPT_DIR/pod-health.sh" || {
    echo "Error: Kroki pod is not healthy. Cannot render." >&2
    exit 1
}

mkdir -p "$STATE_DIR"
date +%s > "$LAST_USE_FILE"

# Infer diagram type from extension when not explicitly provided.
# The kroki CLI does not recognise all common aliases (.mmd, .puml, .pu, etc.)
# so we map them here before handing off.
if [[ -z "$DIAGRAM_TYPE" ]]; then
    case "${SOURCE##*.}" in
        puml|pu|iuml)  DIAGRAM_TYPE="plantuml" ;;
        mmd)           DIAGRAM_TYPE="mermaid" ;;
        gv)            DIAGRAM_TYPE="graphviz" ;;
        adia)          DIAGRAM_TYPE="actdiag" ;;
        bdia)          DIAGRAM_TYPE="blockdiag" ;;
        ndia)          DIAGRAM_TYPE="nwdiag" ;;
        pdia)          DIAGRAM_TYPE="packetdiag" ;;
        rdia)          DIAGRAM_TYPE="rackdiag" ;;
        sdia)          DIAGRAM_TYPE="seqdiag" ;;
        nml)           DIAGRAM_TYPE="nomnoml" ;;
        pik)           DIAGRAM_TYPE="pikchr" ;;
        sbob)          DIAGRAM_TYPE="svgbob" ;;
        dsl)           DIAGRAM_TYPE="structurizr" ;;
        vhdl)          DIAGRAM_TYPE="symbolator" ;;
        tex)           DIAGRAM_TYPE="tikz" ;;
        uxf)           DIAGRAM_TYPE="umlet" ;;
    esac
fi

# Render base SVG to a scratch path.
BASE_TMP="$(mktemp --suffix=".svg")"
trap 'rm -f "$BASE_TMP" "${KROKI_STDERR:-}"' EXIT INT TERM
KROKI_ARGS=("convert" "$SOURCE" "--format" "$OUTPUT_FORMAT" "--out-file" "$BASE_TMP")
if [[ -n "$DIAGRAM_TYPE" ]]; then
    KROKI_ARGS+=("--type" "$DIAGRAM_TYPE")
fi

KROKI_STDERR="$(mktemp)"
if ! "$KROKI_CLI" "${KROKI_ARGS[@]}" 2>"$KROKI_STDERR"; then
    cat "$KROKI_STDERR" >&2
    rm -f "$KROKI_STDERR" "$BASE_TMP"
    echo "Error: Kroki render failed for $SOURCE" >&2
    exit 2
fi
rm -f "$KROKI_STDERR"

if [[ ! -s "$BASE_TMP" ]]; then
    echo "Error: Render produced empty output for $SOURCE" >&2
    rm -f "$BASE_TMP"
    exit 2
fi

# Resolve output paths for the requested mode(s).
emit_light=0
emit_dark=0
emit_single=0
case "$MODE" in
    dual)   emit_light=1; emit_dark=1 ;;
    light)  emit_light=1 ;;
    dark)   emit_dark=1 ;;
    single) emit_single=1 ;;
esac

written=()

if (( emit_single == 1 )); then
    OUT="$OUTPUT_DIR/${SOURCE_NAME}.${OUTPUT_FORMAT}"
    mv "$BASE_TMP" "$OUT"
    written+=("$OUT")
fi

if (( emit_light == 1 )); then
    OUT="$OUTPUT_DIR/${SOURCE_NAME}.light.${OUTPUT_FORMAT}"
    if (( emit_dark == 1 )); then
        cp "$BASE_TMP" "$OUT"
    else
        mv "$BASE_TMP" "$OUT"
    fi
    written+=("$OUT")
fi

if (( emit_dark == 1 )); then
    OUT="$OUTPUT_DIR/${SOURCE_NAME}.dark.${OUTPUT_FORMAT}"
    if ! python3 "$PY_UTIL" --op dark-remap --in "$BASE_TMP" --out "$OUT"; then
        echo "Error: dark-remap failed for $SOURCE" >&2
        rm -f "$BASE_TMP" "$OUTPUT_DIR/${SOURCE_NAME}.light.${OUTPUT_FORMAT}"
        exit 2
    fi
    written+=("$OUT")
fi

for p in "${written[@]}"; do
    echo "$p"
done
