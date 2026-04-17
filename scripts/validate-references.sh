#!/usr/bin/env bash
# validate-references.sh — Render each ```<lang> snippet in reference docs.
#
# Usage:
#   validate-references.sh <markdown-file-or-glob> [more-files...]
#
# Scans each Markdown file for code fences tagged with a Kroki-known language
# and pipes each snippet to render.sh. Reports PASS / FAIL per snippet.
#
# Exit codes:
#   0 — all snippets rendered (or none found)
#   1 — at least one snippet failed to render
#   2 — usage error

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: validate-references.sh <markdown-file...>" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENDER="$SCRIPT_DIR/render.sh"

# Languages Kroki knows about (superset — render.sh --type dispatches).
KROKI_LANGS="plantuml c4plantuml mermaid graphviz d2 actdiag blockdiag bpmn \
bytefield dbml diagramsnet ditaa erd excalidraw nomnoml nwdiag packetdiag \
pikchr rackdiag seqdiag structurizr svgbob symbolator tikz umlet vega \
vegalite wavedrom wireviz"

total=0
fail=0

for md in "$@"; do
    if [[ ! -f "$md" ]]; then
        echo "  SKIP  $md (not a file)"
        continue
    fi

    # Extract fenced code blocks with their language tag using awk.
    # Use process substitution (< <(...)) so the while loop runs in THIS shell,
    # allowing $snippet, $lang, $total, and $fail to persist across iterations.
    lang=""
    snippet=""
    while IFS= read -r line; do
        if [[ "$line" == ===BEGIN===* ]]; then
            lang="${line#===BEGIN===}"
            snippet=""
            continue
        fi
        if [[ "$line" == ===END=== ]]; then
            tmp="$(mktemp --suffix=".$lang")"
            printf '%s' "$snippet" > "$tmp"
            ((++total))
            if "$RENDER" "$tmp" --type "$lang" --mode single --out "$(dirname "$tmp")" >/dev/null 2>&1; then
                echo "  PASS  $md [$lang]"
            else
                echo "  FAIL  $md [$lang]" >&2
                ((++fail))
            fi
            mv "$tmp" ~/.local/share/Trash/files/"$(basename "$tmp")" 2>/dev/null || true
            continue
        fi
        snippet="${snippet}${line}"$'\n'
    done < <(awk -v langs=" $KROKI_LANGS " '
        /^```/ {
            if (in_fence) {
                if (lang != "" && index(langs, " " lang " ")) {
                    print "===BEGIN===" lang
                    print buf
                    print "===END==="
                }
                in_fence = 0
                lang = ""
                buf = ""
            } else {
                in_fence = 1
                lang = substr($0, 4)
                sub(/[[:space:]].*$/, "", lang)
            }
            next
        }
        in_fence {
            buf = buf $0 "\n"
        }
    ' "$md")
done

if (( fail > 0 )); then
    echo "validate-references: $fail / $total failed" >&2
    exit 1
fi

echo "validate-references: all snippets rendered"
exit 0
