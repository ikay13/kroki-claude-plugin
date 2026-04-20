#!/usr/bin/env bash
# smoke.sh — Verify Kroki rendering pipeline works end-to-end.
#
# Usage:
#   ./tests/smoke.sh          Quick mode (5 core fixtures)
#   ./tests/smoke.sh --full   Full mode (all fixtures in tests/fixtures/)
#
# Checks per fixture:
#   - render.sh exits 0
#   - Output file exists and is >0 bytes
#   - Output file starts with valid SVG header (<svg or <?xml)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RENDER="$PLUGIN_DIR/scripts/render.sh"
FIXTURES_DIR="$PLUGIN_DIR/tests/fixtures"
OUTPUT_DIR=$(mktemp -d /tmp/kroki-smoke-XXXXXX)
INT_DIR=""
shopt -s nullglob
cleanup_smoke() { [[ -n "$OUTPUT_DIR" ]] && rm -rf "$OUTPUT_DIR"; [[ -n "$INT_DIR" ]] && rm -rf "$INT_DIR"; }
trap cleanup_smoke EXIT INT TERM

FULL_MODE=false
if [[ "${1:-}" == "--full" ]]; then
    FULL_MODE=true
fi

# Language type mapping (filename stem -> kroki type)
declare -A TYPE_MAP=(
    [plantuml]=plantuml
    [mermaid]=mermaid
    [graphviz]=graphviz
    [d2]=d2
    [c4plantuml]=c4plantuml
    [actdiag]=actdiag
    [blockdiag]=blockdiag
    [bpmn]=bpmn
    [bytefield]=bytefield
    [dbml]=dbml
    [diagramsnet]=diagramsnet
    [ditaa]=ditaa
    [erd]=erd
    [excalidraw]=excalidraw
    [nomnoml]=nomnoml
    [nwdiag]=nwdiag
    [packetdiag]=packetdiag
    [pikchr]=pikchr
    [rackdiag]=rackdiag
    [seqdiag]=seqdiag
    [structurizr]=structurizr
    [svgbob]=svgbob
    [symbolator]=symbolator
    [tikz]=tikz
    [umlet]=umlet
    [vega]=vega
    [vegalite]=vegalite
    [wavedrom]=wavedrom
    [wireviz]=wireviz
)

CORE_FIXTURES=(plantuml mermaid graphviz d2 c4plantuml)

pass=0
fail=0
skip=0
total=0

run_fixture() {
    local name="$1"
    local fixture_file="$FIXTURES_DIR/${name}.fixture.txt"
    local diagram_type="${TYPE_MAP[$name]:-$name}"

    if [[ ! -f "$fixture_file" ]]; then
        printf "  SKIP  %-20s (fixture not found)\n" "$name"
        ((++skip))
        return
    fi

    ((++total))

    local output
    if ! output=$("$RENDER" "$fixture_file" --type "$diagram_type" --format svg --out "$OUTPUT_DIR" 2>&1); then
        printf "  FAIL  %-20s (render error: %s)\n" "$name" "$output"
        ((++fail))
        return
    fi

    local light="$OUTPUT_DIR/${name}.fixture.light.svg"
    local dark="$OUTPUT_DIR/${name}.fixture.dark.svg"

    for variant in "$light" "$dark"; do
        if [[ ! -s "$variant" ]]; then
            printf "  FAIL  %-20s (missing/empty: %s)\n" "$name" "$(basename "$variant")"
            ((++fail))
            return
        fi
        local header
        header=$(head -c 256 "$variant")
        if [[ "$header" != *"<svg"* ]] && [[ "$header" != *"<?xml"* ]]; then
            printf "  FAIL  %-20s (invalid SVG header: %s)\n" "$name" "$(basename "$variant")"
            ((++fail))
            return
        fi
    done

    local light_bytes dark_bytes
    light_bytes=$(wc -c < "$light")
    dark_bytes=$(wc -c < "$dark")
    printf "  PASS  %-20s (light=%s dark=%s bytes)\n" "$name" "$light_bytes" "$dark_bytes"
    ((++pass))
}

echo "Kroki Smoke Test"
echo "================"
echo ""

# Pod health check first
echo "Checking pod health..."
if ! "$PLUGIN_DIR/scripts/pod-health.sh"; then
    echo "BLOCKED: Pod unavailable. Cannot run smoke tests."
    exit 1
fi
echo ""

if $FULL_MODE; then
    echo "Mode: FULL (all fixtures)"
    for fixture_file in "$FIXTURES_DIR"/*.fixture.txt; do
        name=$(basename "$fixture_file" .fixture.txt)
        run_fixture "$name"
    done
else
    echo "Mode: QUICK (5 core fixtures)"
    for name in "${CORE_FIXTURES[@]}"; do
        run_fixture "$name"
    done
fi

# Kroki-session round-trip (only in --full mode).
if $FULL_MODE; then
    echo ""
    echo "=== kroki-session round-trip (synthetic vault) ==="
    ROUND_TRIP_DIR=$(mktemp -d)
    trap "rm -rf $ROUND_TRIP_DIR" EXIT
    ROUND_TRIP_PROJECT="$ROUND_TRIP_DIR/TestProject"
    mkdir -p "$ROUND_TRIP_PROJECT/diagrams" "$ROUND_TRIP_PROJECT/sessions"
    cd "$ROUND_TRIP_PROJECT"
    git init -q -b main
    git config user.email "smoke@test"
    git config user.name "Smoke"

    # Create initial commit with one diagram
    cat > diagrams/arch-smoke.puml <<'PUML'
' Smoke test: minimal PlantUML
@startuml
A -> B: hello
@enduml
PUML
    git add .
    git commit -q -m "initial"

    # Create a session log for embed target
    cat > sessions/2026-04-20-TestProject-session-00.md <<'MD'
---
project: TestProject
session_nn: 0
date: 2026-04-20
profile: [se-project]
status: active
session_goal: smoke test
---

# Session 00 — 2026-04-20: smoke

## what-was-done

smoke test

## next-steps

- none
MD

    # Now modify the diagram (creates a changed file)
    cat > diagrams/arch-smoke.puml <<'PUML'
' Smoke test: minimal PlantUML
@startuml
A -> C: modified
@enduml
PUML

    # Run mode=end
    cd "$PLUGIN_DIR"
    if ./scripts/session-end.sh --project TestProject --vault-path "$ROUND_TRIP_PROJECT" >/dev/null 2>&1; then
        # Verify: SVG outputs were created
        if [[ -s "$ROUND_TRIP_PROJECT/diagrams/arch-smoke.light.svg" ]] && [[ -s "$ROUND_TRIP_PROJECT/diagrams/arch-smoke.dark.svg" ]]; then
            echo "  [OK]  kroki-session round-trip: SVG files rendered"
        else
            echo "  [FAIL] kroki-session round-trip: SVG files not rendered"
            exit 1
        fi
        # Verify: INDEX.md was regenerated
        if [[ -s "$ROUND_TRIP_PROJECT/diagrams/INDEX.md" ]]; then
            echo "  [OK]  kroki-session round-trip: INDEX.md regenerated"
        else
            echo "  [FAIL] kroki-session round-trip: INDEX.md not generated"
            exit 1
        fi
    else
        echo "  [FAIL] kroki-session round-trip: session-end.sh failed"
        exit 1
    fi
    cd "$PLUGIN_DIR"
fi

# Python unit tests (Plan 2)
if command -v python3 >/dev/null 2>&1; then
    echo ""
    echo "=== Python unit tests ==="
    if ( cd "$PLUGIN_DIR" && python3 -m pytest tests/test_kroki_util.py -q ); then
        echo "Python tests: PASS"
    else
        echo "Python tests: FAIL"
        ((++fail))
    fi
fi

# Obsidian integration check (Plan 3)
echo ""
echo "=== Obsidian integration check ==="
INT_DIR=$(mktemp -d /tmp/kroki-obsidian-it-XXXXXX)

INT_DIAGRAMS="$INT_DIR/diagrams"
mkdir -p "$INT_DIAGRAMS"

# Copy 2 core fixtures so they parse as valid diagram sources.
cp "$FIXTURES_DIR/plantuml.fixture.txt" "$INT_DIAGRAMS/arch-demo-plantuml.puml"
cp "$FIXTURES_DIR/d2.fixture.txt"       "$INT_DIAGRAMS/arch-demo-d2.d2"

# Prepend a purpose comment so update-index.sh has something to extract.
sed -i '1i '"'"' Demo PlantUML diagram for smoke test' "$INT_DIAGRAMS/arch-demo-plantuml.puml"
sed -i '1i // Demo D2 diagram for smoke test'             "$INT_DIAGRAMS/arch-demo-d2.d2"

INT_PASS=true
if ! "$RENDER" "$INT_DIAGRAMS/arch-demo-plantuml.puml" --type plantuml --out "$INT_DIAGRAMS" >/dev/null 2>&1; then
    echo "  FAIL  integration: render plantuml"
    INT_PASS=false
fi
if ! "$RENDER" "$INT_DIAGRAMS/arch-demo-d2.d2" --type d2 --out "$INT_DIAGRAMS" >/dev/null 2>&1; then
    echo "  FAIL  integration: render d2"
    INT_PASS=false
fi

if ! "$PLUGIN_DIR/scripts/update-index.sh" "$INT_DIAGRAMS" >/dev/null 2>&1; then
    echo "  FAIL  integration: update-index.sh"
    INT_PASS=false
fi

if [[ ! -f "$INT_DIAGRAMS/INDEX.md" ]]; then
    echo "  FAIL  integration: INDEX.md not created"
    INT_PASS=false
else
    for name in arch-demo-plantuml arch-demo-d2; do
        if ! grep -q "$name" "$INT_DIAGRAMS/INDEX.md"; then
            echo "  FAIL  integration: $name missing from INDEX.md"
            INT_PASS=false
        fi
    done
fi

echo "# Test" > "$INT_DIR/test.md"
if ! "$PLUGIN_DIR/scripts/embed-in-md.sh" "$INT_DIR/test.md" "arch-demo-plantuml" --caption "Demo" >/dev/null 2>&1; then
    echo "  FAIL  integration: embed-in-md.sh first call"
    INT_PASS=false
fi
if ! grep -qF "[[arch-demo-plantuml.light.svg]]" "$INT_DIR/test.md"; then
    echo "  FAIL  integration: light wikilink missing"
    INT_PASS=false
fi
if ! grep -qF "Figure -- Demo" "$INT_DIR/test.md"; then
    echo "  FAIL  integration: caption missing"
    INT_PASS=false
fi
"$PLUGIN_DIR/scripts/embed-in-md.sh" "$INT_DIR/test.md" "arch-demo-plantuml" --caption "Demo" >/dev/null 2>&1 || true
dup_count=$(grep -cF "[[arch-demo-plantuml.light.svg]]" "$INT_DIR/test.md" || echo 0)
if [[ "$dup_count" -ne 1 ]]; then
    echo "  FAIL  integration: embed not idempotent (count=$dup_count)"
    INT_PASS=false
fi

if $INT_PASS; then
    echo "  PASS  integration: render -> update-index -> embed"
else
    ((++fail))
fi

echo ""
echo "Results: $pass passed, $fail failed, $skip skipped ($total total)"

if (( fail > 0 )); then
    exit 1
fi
exit 0
