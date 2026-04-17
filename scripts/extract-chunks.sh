#!/usr/bin/env bash
# extract-chunks.sh — Pull every fenced diagram code block from a markdown file.
#
# Usage:
#   extract-chunks.sh <input.md> [--out <dir>]
#
# Recognized fence shapes (language tag is case-insensitive):
#   ```plantuml          → 01-plantuml.puml
#   ```{.puml}           → 01-plantuml.puml
#   ```mermaid           → 02-mermaid.mmd
#   ```{.dot}            → 03-graphviz.dot
#   ```d2                → 04-d2.d2
#
# Output: <out>/NN-<lang>.<ext>, one file per chunk. NN is zero-padded 2-digit.
#
# Exit codes:
#   0 — chunks extracted (count printed to stderr)
#   1 — no chunks found
#   2 — input file not readable
#   3 — usage error

set -euo pipefail

INPUT=""
OUT_DIR="./extracted"

usage() {
    echo "Usage: extract-chunks.sh <input.md> [--out <dir>]" >&2
    exit 3
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out)     OUT_DIR="$2"; shift 2 ;;
        --help|-h) usage ;;
        -*)        echo "Unknown option: $1" >&2; usage ;;
        *)         INPUT="$1"; shift ;;
    esac
done

if [[ -z "$INPUT" ]]; then
    usage
fi

if [[ ! -r "$INPUT" ]]; then
    echo "Error: input not readable: $INPUT" >&2
    exit 2
fi

mkdir -p "$OUT_DIR"

# Language tag → (canonical-name, extension)
canon() {
    case "${1,,}" in
        plantuml|puml|pu|iuml)  echo "plantuml puml" ;;
        graphviz|dot|gv)        echo "graphviz dot" ;;
        mermaid|mmd)            echo "mermaid mmd" ;;
        d2)                     echo "d2 d2" ;;
        c4plantuml|c4)          echo "c4plantuml puml" ;;
        actdiag|adia)           echo "actdiag adia" ;;
        blockdiag|bdia)         echo "blockdiag bdia" ;;
        nwdiag|ndia)            echo "nwdiag ndia" ;;
        packetdiag|pdia)        echo "packetdiag pdia" ;;
        rackdiag|rdia)          echo "rackdiag rdia" ;;
        seqdiag|sdia)           echo "seqdiag sdia" ;;
        erd)                    echo "erd erd" ;;
        nomnoml|nml)            echo "nomnoml nml" ;;
        pikchr|pik)             echo "pikchr pik" ;;
        svgbob|sbob)            echo "svgbob sbob" ;;
        ditaa)                  echo "ditaa ditaa" ;;
        dbml)                   echo "dbml dbml" ;;
        bpmn)                   echo "bpmn bpmn" ;;
        bytefield)              echo "bytefield bytefield" ;;
        diagramsnet)            echo "diagramsnet drawio" ;;
        excalidraw)             echo "excalidraw excalidraw" ;;
        structurizr)            echo "structurizr dsl" ;;
        symbolator|vhdl)        echo "symbolator vhdl" ;;
        tikz)                   echo "tikz tex" ;;
        umlet)                  echo "umlet uxf" ;;
        vega)                   echo "vega vega" ;;
        vegalite|vega-lite)     echo "vegalite vegalite" ;;
        wavedrom)               echo "wavedrom wavedrom" ;;
        wireviz)                echo "wireviz wireviz" ;;
        *) return 1 ;;
    esac
}

# AWK extracts every fence block whose info-string matches one of our tags.
# Emits one record per chunk, NUL-separated: <lang>\0<body>\0
# We write to a temp file because $() command substitution strips NUL bytes.
EXTRACTED_TMP=$(mktemp)
awk '
function emit(   tag) {
    tag = lang
    sub(/^\{\./, "", tag); sub(/\}.*$/, "", tag)
    sub(/[ \t].*$/, "", tag)
    if (tag == "") return
    printf "%s\0%s\0", tolower(tag), body
}
/^[ \t]*```/ {
    if (in_block) {
        emit()
        in_block = 0
        body = ""
        lang = ""
        next
    }
    line = $0
    sub(/^[ \t]*```/, "", line)
    if (line == "") next
    lang = line
    in_block = 1
    next
}
in_block { body = body $0 "\n" }
' "$INPUT" > "$EXTRACTED_TMP"

if [[ ! -s "$EXTRACTED_TMP" ]]; then
    mv "$EXTRACTED_TMP" ~/.local/share/Trash/files/ 2>/dev/null || true
    echo "No fenced code blocks found." >&2
    exit 1
fi

count=0
saved=0

# Iterate over NUL-separated <lang>\0<body>\0 pairs
while IFS= read -r -d '' lang && IFS= read -r -d '' body; do
    ((++count))
    if ! mapping=$(canon "$lang"); then
        printf '  skip  chunk %02d  (unrecognized lang: %s)\n' "$count" "$lang" >&2
        continue
    fi
    canonical="${mapping% *}"
    ext="${mapping##* }"
    ((++saved))
    out_file=$(printf '%s/%02d-%s.%s' "$OUT_DIR" "$saved" "$canonical" "$ext")
    printf '%s' "$body" > "$out_file"
    printf '  save  %s\n' "$out_file" >&2
done < "$EXTRACTED_TMP"

mv "$EXTRACTED_TMP" ~/.local/share/Trash/files/ 2>/dev/null || true

if (( saved == 0 )); then
    echo "No recognized diagram chunks found (saw $count fenced block(s))." >&2
    exit 1
fi

echo "Extracted $saved chunk(s) to $OUT_DIR (scanned $count fenced block(s))." >&2
