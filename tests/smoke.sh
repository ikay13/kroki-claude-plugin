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
ED_SCRATCH=""
shopt -s nullglob
cleanup_smoke() { [[ -n "$OUTPUT_DIR" ]] && rm -rf "$OUTPUT_DIR"; [[ -n "$INT_DIR" ]] && rm -rf "$INT_DIR"; [[ -n "$ED_SCRATCH" ]] && rm -rf "$ED_SCRATCH"; }
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

# Restore full cleanup trap now that ROUND_TRIP_DIR is done.
trap cleanup_smoke EXIT INT TERM

# --- Plan 5c editor-lock lifecycle smoke tests (Tasks 10-11) ---
if $FULL_MODE; then
    echo ""
    echo "=== editor-lock lifecycle (Tasks 10-11) ==="

    ED_SCRATCH=$(mktemp -d /tmp/kroki-editor-smoke-XXXXXX)

    ED_HOME="$ED_SCRATCH/home"
    mkdir -p "$ED_HOME"

    # Stubs on PATH for pod-health.sh and xdg-open.
    ED_STUBS="$ED_SCRATCH/stubs"
    mkdir -p "$ED_STUBS"
    cat > "$ED_STUBS/pod-health.sh" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
    chmod +x "$ED_STUBS/pod-health.sh"
    cat > "$ED_STUBS/xdg-open" <<'STUB'
#!/usr/bin/env bash
echo "xdg-open $*" >> "${HOME:-/tmp}/xdg-open.log"
exit 0
STUB
    chmod +x "$ED_STUBS/xdg-open"

    # Snapshot current environment; we set HOME/PATH/DISPLAY for each scenario and restore after.
    SAVED_HOME="${HOME-}"
    SAVED_PATH="$PATH"
    SAVED_DISPLAY="${DISPLAY-__unset__}"
    SAVED_WAYLAND="${WAYLAND_DISPLAY-__unset__}"

    export HOME="$ED_HOME"
    export PATH="$ED_STUBS:$PATH"
    export DISPLAY=":99"
    unset WAYLAND_DISPLAY

    ED_LOCK="$ED_HOME/.kroki-plugin/.active-editor.lock"

    ED_FIXTURE="$ED_SCRATCH/arch-smoke.puml"
    cat > "$ED_FIXTURE" <<'PUML'
@startuml
A -> B
@enduml
PUML

    # S1: editor-open.sh <file> writes lock with source_path.
    "$PLUGIN_DIR/scripts/editor-open.sh" "$ED_FIXTURE" >/dev/null
    if [[ -f "$ED_LOCK" ]] && python3 -c "import json,sys; d=json.load(open('$ED_LOCK')); sys.exit(0 if d['source_path'] == '$(realpath "$ED_FIXTURE")' else 1)"; then
        echo "  [OK]  S1: editor-open.sh writes lock with source_path matching abspath"
    else
        echo "  [FAIL] S1: lock content mismatch or missing"
        cat "$ED_LOCK" 2>/dev/null || echo "  (lock missing)"
        exit 1
    fi
    (cd "$PLUGIN_DIR" && HOME="$ED_HOME" python3 -m lib.kroki_session.lock close) >/dev/null

    # S2: blank session (no arg) writes lock with source_path: null.
    "$PLUGIN_DIR/scripts/editor-open.sh" >/dev/null
    if [[ -f "$ED_LOCK" ]] && python3 -c "import json,sys; d=json.load(open('$ED_LOCK')); sys.exit(0 if d['source_path'] is None else 1)"; then
        echo "  [OK]  S2: blank session lock has source_path: null"
    else
        echo "  [FAIL] S2: blank session lock content mismatch"
        exit 1
    fi

    # S3: editor-open while lock held → exit 3.
    S3_STDERR="$ED_SCRATCH/s3.stderr"
    if "$PLUGIN_DIR/scripts/editor-open.sh" "$ED_FIXTURE" 2>"$S3_STDERR"; then
        echo "  [FAIL] S3: editor-open.sh should have exited 3 with lock held"
        exit 1
    else
        S3_RC=$?
        if [[ $S3_RC -eq 3 ]] && grep -qi "held\|lock" "$S3_STDERR"; then
            echo "  [OK]  S3: editor-open.sh exits 3 when lock held; stderr mentions lock"
        else
            echo "  [FAIL] S3: expected exit 3 with 'held/lock' in stderr; got rc=$S3_RC"
            cat "$S3_STDERR"
            exit 1
        fi
    fi
    (cd "$PLUGIN_DIR" && HOME="$ED_HOME" python3 -m lib.kroki_session.lock close) >/dev/null

    # S4: headless refusal.
    unset DISPLAY
    unset WAYLAND_DISPLAY
    S4_STDERR="$ED_SCRATCH/s4.stderr"
    if "$PLUGIN_DIR/scripts/editor-open.sh" "$ED_FIXTURE" 2>"$S4_STDERR"; then
        echo "  [FAIL] S4: editor-open.sh should have exited 1 when no display"
        exit 1
    else
        S4_RC=$?
        if [[ $S4_RC -eq 1 ]] && grep -qi "graphical" "$S4_STDERR" && [[ ! -f "$ED_LOCK" ]]; then
            echo "  [OK]  S4: editor-open.sh exits 1 when headless; no lock written"
        else
            echo "  [FAIL] S4: expected exit 1 + 'graphical' stderr + no lock"
            cat "$S4_STDERR"
            exit 1
        fi
    fi
    export DISPLAY=":99"

    # S5: pod down refusal.
    cat > "$ED_STUBS/pod-health.sh" <<'STUB'
#!/usr/bin/env bash
exit 1
STUB
    S5_STDERR="$ED_SCRATCH/s5.stderr"
    if "$PLUGIN_DIR/scripts/editor-open.sh" "$ED_FIXTURE" 2>"$S5_STDERR"; then
        echo "  [FAIL] S5: editor-open.sh should have exited 1 when pod down"
        exit 1
    else
        S5_RC=$?
        if [[ $S5_RC -eq 1 ]] && grep -qi "pod" "$S5_STDERR"; then
            echo "  [OK]  S5: editor-open.sh exits 1 when pod down; stderr mentions pod"
        else
            echo "  [FAIL] S5: expected exit 1 + 'pod' in stderr"
            cat "$S5_STDERR"
            exit 1
        fi
    fi
    cat > "$ED_STUBS/pod-health.sh" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB

    # S6: missing source file.
    S6_STDERR="$ED_SCRATCH/s6.stderr"
    if "$PLUGIN_DIR/scripts/editor-open.sh" "$ED_SCRATCH/does-not-exist.puml" 2>"$S6_STDERR"; then
        echo "  [FAIL] S6: editor-open.sh should have exited 1 for missing file"
        exit 1
    else
        S6_RC=$?
        if [[ $S6_RC -eq 1 ]] && grep -qi "not found" "$S6_STDERR"; then
            echo "  [OK]  S6: editor-open.sh exits 1 for missing file"
        else
            echo "  [FAIL] S6: expected exit 1 + 'not found' stderr"
            cat "$S6_STDERR"
            exit 1
        fi
    fi

    # S9: path with spaces.
    ED_SPACED="$ED_SCRATCH/path with spaces.puml"
    cp "$ED_FIXTURE" "$ED_SPACED"
    "$PLUGIN_DIR/scripts/editor-open.sh" "$ED_SPACED" >/dev/null
    if [[ -f "$ED_LOCK" ]] && python3 -c "import json,sys; d=json.load(open('$ED_LOCK')); sys.exit(0 if d['source_path'] == '$(realpath "$ED_SPACED")' else 1)"; then
        echo "  [OK]  S9: editor-open.sh handles path with spaces correctly"
    else
        echo "  [FAIL] S9: lock source_path does not match spaced abspath"
        cat "$ED_LOCK"
        exit 1
    fi
    (cd "$PLUGIN_DIR" && HOME="$ED_HOME" python3 -m lib.kroki_session.lock close) >/dev/null

    # S7: editor-close.sh with lock held clears it and prints source reminder.
    "$PLUGIN_DIR/scripts/editor-open.sh" "$ED_FIXTURE" >/dev/null
    S7_OUTPUT="$ED_SCRATCH/s7.out"
    if "$PLUGIN_DIR/scripts/editor-close.sh" >"$S7_OUTPUT" 2>&1; then
        if [[ ! -f "$ED_LOCK" ]] && grep -q "$(realpath "$ED_FIXTURE")" "$S7_OUTPUT"; then
            echo "  [OK]  S7: editor-close.sh with lock clears it; output mentions source path"
        else
            echo "  [FAIL] S7: lock still present or source path missing from output"
            [[ -f "$ED_LOCK" ]] && echo "  (lock still exists)"
            cat "$S7_OUTPUT"
            exit 1
        fi
    else
        echo "  [FAIL] S7: editor-close.sh exited nonzero while lock held"
        cat "$S7_OUTPUT"
        exit 1
    fi

    # S8: editor-close.sh with no lock.
    S8_OUTPUT="$ED_SCRATCH/s8.out"
    if "$PLUGIN_DIR/scripts/editor-close.sh" >"$S8_OUTPUT" 2>&1; then
        if grep -q "No lock was held" "$S8_OUTPUT"; then
            echo "  [OK]  S8: editor-close.sh with no lock prints 'No lock was held'"
        else
            echo "  [FAIL] S8: expected 'No lock was held' in output"
            cat "$S8_OUTPUT"
            exit 1
        fi
    else
        echo "  [FAIL] S8: editor-close.sh exited nonzero with no lock (should be idempotent)"
        cat "$S8_OUTPUT"
        exit 1
    fi

    # Restore environment.
    if [[ "$SAVED_HOME" != "" ]]; then export HOME="$SAVED_HOME"; else unset HOME; fi
    export PATH="$SAVED_PATH"
    if [[ "$SAVED_DISPLAY" == "__unset__" ]]; then unset DISPLAY; else export DISPLAY="$SAVED_DISPLAY"; fi
    if [[ "$SAVED_WAYLAND" == "__unset__" ]]; then unset WAYLAND_DISPLAY; else export WAYLAND_DISPLAY="$SAVED_WAYLAND"; fi
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
