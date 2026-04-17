#!/usr/bin/env bash
# encode-url.sh — Encode diagram source as a kroki shareable URL.
#
# Usage:
#   encode-url.sh <source_file> [--type <type>] [--format <fmt>] [--endpoint <url>]
#   echo '<source>' | encode-url.sh --type <type> [--format <fmt>] [--endpoint <url>]
#
# Algorithm: base64-url-safe(zlib(utf8(source))) — matches kroki4tcl reference
# implementation at ~/kroki4tcl/kroki4tcl/kroki4tcl.tcl:67-74.
#
# Exit codes:
#   0 — URL printed to stdout
#   2 — bad input (file not found, missing --type for stdin, etc.)
#   3 — usage error

set -euo pipefail

SOURCE=""
DIAGRAM_TYPE=""
OUTPUT_FORMAT="svg"
ENDPOINT="${KROKI_ENDPOINT:-http://localhost:8000}"

usage() {
    echo "Usage: encode-url.sh <source_file> [--type <type>] [--format <fmt>] [--endpoint <url>]" >&2
    echo "       echo '<source>' | encode-url.sh --type <type> [--format <fmt>] [--endpoint <url>]" >&2
    exit 3
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)     DIAGRAM_TYPE="$2"; shift 2 ;;
        --format)   OUTPUT_FORMAT="$2"; shift 2 ;;
        --endpoint) ENDPOINT="$2"; shift 2 ;;
        --help|-h)  usage ;;
        -*)         echo "Unknown option: $1" >&2; usage ;;
        *)          SOURCE="$1"; shift ;;
    esac
done

# Read source
if [[ -n "$SOURCE" ]]; then
    if [[ ! -f "$SOURCE" ]]; then
        echo "Error: source file not found: $SOURCE" >&2
        exit 2
    fi
    # Infer type from extension if not given
    if [[ -z "$DIAGRAM_TYPE" ]]; then
        ext="${SOURCE##*.}"
        case "$ext" in
            puml|plantuml|pu|iuml) DIAGRAM_TYPE="plantuml" ;;
            dot|gv)                DIAGRAM_TYPE="graphviz" ;;
            mmd|mermaid)           DIAGRAM_TYPE="mermaid" ;;
            d2)                    DIAGRAM_TYPE="d2" ;;
            adia)                  DIAGRAM_TYPE="actdiag" ;;
            bdia)                  DIAGRAM_TYPE="blockdiag" ;;
            ndia)                  DIAGRAM_TYPE="nwdiag" ;;
            pdia)                  DIAGRAM_TYPE="packetdiag" ;;
            rdia)                  DIAGRAM_TYPE="rackdiag" ;;
            sdia)                  DIAGRAM_TYPE="seqdiag" ;;
            erd)                   DIAGRAM_TYPE="erd" ;;
            nml)                   DIAGRAM_TYPE="nomnoml" ;;
            pik)                   DIAGRAM_TYPE="pikchr" ;;
            sbob)                  DIAGRAM_TYPE="svgbob" ;;
            dbml)                  DIAGRAM_TYPE="dbml" ;;
            bpmn)                  DIAGRAM_TYPE="bpmn" ;;
            *)
                echo "Error: cannot infer --type from extension '.$ext'. Pass --type explicitly." >&2
                exit 2
                ;;
        esac
    fi
    SOURCE_TEXT="$(cat "$SOURCE")"
else
    if [[ -z "$DIAGRAM_TYPE" ]]; then
        echo "Error: --type is required when reading source from stdin." >&2
        exit 2
    fi
    SOURCE_TEXT="$(cat)"
fi

# Encode via Python (zlib + base64-url-safe; matches kroki4tcl algorithm)
ENCODED=$(printf '%s' "$SOURCE_TEXT" | python3 -c '
import sys, zlib, base64
data = sys.stdin.buffer.read()
compressed = zlib.compress(data, 9)
encoded = base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")
sys.stdout.write(encoded)
')

printf '%s/%s/%s/%s\n' "${ENDPOINT%/}" "$DIAGRAM_TYPE" "$OUTPUT_FORMAT" "$ENCODED"
