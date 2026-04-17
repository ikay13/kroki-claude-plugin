#!/usr/bin/env bash
# embed-in-md.sh — Insert a <div class="kroki-dual"> block under a section heading.
#
# Usage:
#   embed-in-md.sh <target.md> <diagram-basename> [--section "## Heading"] [--caption "text"]
#
# Inserts:
#   <div class="kroki-dual">
#   ![[<basename>.light.svg]]
#   ![[<basename>.dark.svg]]
#   </div>
#   *Figure -- <caption>*          (only if --caption given)
#
# Idempotent via grep on [[<basename>.light.svg]]. Default section: "## Diagrams".
# Creates the section at EOF if absent; otherwise inserts immediately after
# the existing section heading.
#
# Exit codes:
#   0 — embedded or already present
#   3 — usage error

set -euo pipefail

usage() {
    cat <<EOF
Usage: embed-in-md.sh <target.md> <diagram-basename> [--section "## Heading"] [--caption "text"]

Inserts a <div class="kroki-dual"> block with dual .light.svg + .dark.svg wikilinks.
Idempotent via grep on <basename>.light.svg. Default section: "## Diagrams".
EOF
    exit 3
}

TARGET=""
BASENAME=""
SECTION="## Diagrams"
CAPTION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --section) SECTION="$2"; shift 2 ;;
        --caption) CAPTION="$2"; shift 2 ;;
        --help|-h) usage ;;
        -*)
            echo "Unknown option: $1" >&2
            usage
            ;;
        *)
            if [[ -z "$TARGET" ]]; then
                TARGET="$1"
            elif [[ -z "$BASENAME" ]]; then
                BASENAME="$1"
            else
                echo "Unexpected arg: $1" >&2
                usage
            fi
            shift
            ;;
    esac
done

if [[ -z "$TARGET" || -z "$BASENAME" ]]; then
    usage
fi

if [[ ! -f "$TARGET" ]]; then
    echo "Error: target file not found: $TARGET" >&2
    exit 3
fi

# Idempotency check (fixed-string grep)
if grep -qF "[[${BASENAME}.light.svg]]" "$TARGET"; then
    echo "OK: already embedded: $BASENAME"
    exit 0
fi

# Build the block with embedded newlines.
# Blank lines inside <div>...</div> are REQUIRED so Obsidian's CommonMark
# renderer treats the wikilinks as markdown (not raw HTML). Without the blank
# lines, the div opens an HTML block and the ![[...]] wikilinks render as
# literal text instead of embedded images.
BLOCK='<div class="kroki-dual">

![['"${BASENAME}"'.light.svg]]
![['"${BASENAME}"'.dark.svg]]

</div>'
if [[ -n "$CAPTION" ]]; then
    BLOCK="${BLOCK}
*Figure -- ${CAPTION}*"
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

if grep -qxF "$SECTION" "$TARGET"; then
    # Insert BLOCK immediately after the first line exactly matching $SECTION.
    # awk with ENVIRON preserves embedded newlines in BLOCK.
    export BLOCK
    awk -v section="$SECTION" '
        BEGIN { inserted = 0 }
        {
            print
            if (!inserted && $0 == section) {
                print ""
                print ENVIRON["BLOCK"]
                inserted = 1
            }
        }
    ' "$TARGET" > "$TMP"
    unset BLOCK
    echo "Embedded under existing section: $BASENAME"
else
    # Append section + block at EOF.
    cat "$TARGET" > "$TMP"
    # Ensure trailing newline.
    if [[ -s "$TMP" ]] && [[ "$(tail -c1 "$TMP" | od -An -tx1 | tr -d ' ')" != "0a" ]]; then
        echo "" >> "$TMP"
    fi
    {
        echo ""
        echo "$SECTION"
        echo ""
        echo "$BLOCK"
    } >> "$TMP"
    echo "Created section and embedded: $BASENAME"
fi

mv "$TMP" "$TARGET"
trap - EXIT
