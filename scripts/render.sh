#!/usr/bin/env bash
# render.sh — Render diagram source to SVG via Kroki CLI.
#
# Usage: render.sh <source_file> [--type <type>] [--format <fmt>] [--out <dir>]
#
# Defaults:
#   --type: inferred from file extension
#   --format: svg
#   --out: directory of source file
#
# Behavior:
#   1. Check pod health (auto-start if needed)
#   2. Render via kroki CLI to temp file
#   3. Atomic move to final path
#   4. Save source alongside render if source is stdin/pipe
#
# Exit codes:
#   0 — render succeeded
#   1 — pod unhealthy (after recovery attempts)
#   2 — render failed (syntax error, timeout, etc.)
#   3 — usage error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KROKI_CLI="${KROKI_CLI:-$HOME/go/bin/kroki}"
STATE_DIR="${KROKI_STATE_DIR:-$HOME/.kroki-plugin}"
LAST_USE_FILE="$STATE_DIR/.last-use"

usage() {
    echo "Usage: render.sh <source_file> [--type <type>] [--format <fmt>] [--out <dir>]"
    echo ""
    echo "Options:"
    echo "  --type    Diagram type (plantuml, mermaid, graphviz, d2, etc.)"
    echo "            Default: inferred from file extension"
    echo "  --format  Output format (svg, png, pdf). Default: svg"
    echo "  --out     Output directory. Default: same as source file"
    exit 3
}

# Parse args
SOURCE=""
DIAGRAM_TYPE=""
OUTPUT_FORMAT="svg"
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)   DIAGRAM_TYPE="$2"; shift 2 ;;
        --format) OUTPUT_FORMAT="$2"; shift 2 ;;
        --out)    OUTPUT_DIR="$2"; shift 2 ;;
        --help|-h) usage ;;
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

# Derive output path
SOURCE_BASE="$(basename "$SOURCE")"
SOURCE_NAME="${SOURCE_BASE%.*}"
SOURCE_DIR="$(cd "$(dirname "$SOURCE")" && pwd)"

if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="$SOURCE_DIR"
fi
mkdir -p "$OUTPUT_DIR"

OUTPUT_FILE="$OUTPUT_DIR/${SOURCE_NAME}.${OUTPUT_FORMAT}"
TEMP_FILE="${OUTPUT_FILE}.tmp"

# Step 1: Pod health check
"$SCRIPT_DIR/pod-health.sh" || {
    echo "Error: Kroki pod is not healthy. Cannot render." >&2
    exit 1
}

# Touch last-use for watchdog
mkdir -p "$STATE_DIR"
date +%s > "$LAST_USE_FILE"

# Step 2: Build kroki CLI args
KROKI_ARGS=("convert" "$SOURCE" "--format" "$OUTPUT_FORMAT" "--out-file" "$TEMP_FILE")

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

if [[ -n "$DIAGRAM_TYPE" ]]; then
    KROKI_ARGS+=("--type" "$DIAGRAM_TYPE")
fi

# Step 3: Render to temp file (atomic write pattern)
KROKI_STDERR="$(mktemp)"
if ! "$KROKI_CLI" "${KROKI_ARGS[@]}" 2>"$KROKI_STDERR"; then
    cat "$KROKI_STDERR" >&2
    rm -f "$KROKI_STDERR" "$TEMP_FILE"
    echo "Error: Kroki render failed for $SOURCE" >&2
    exit 2
fi
rm -f "$KROKI_STDERR"

# Step 4: Verify output
if [[ ! -s "$TEMP_FILE" ]]; then
    echo "Error: Render produced empty output for $SOURCE" >&2
    rm -f "$TEMP_FILE"
    exit 2
fi

# Step 5: Atomic move
mv "$TEMP_FILE" "$OUTPUT_FILE"

echo "$OUTPUT_FILE"
