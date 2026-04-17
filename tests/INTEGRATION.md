# Integration Test Scenarios

Manual walkthrough scenarios. Run before tagging a release. Each has a
precondition, steps, and explicit verification criteria. If a step fails,
capture the deviation in the session log and file it as a bug.

## Scenario 1 — Ad-hoc render

**Precondition:** Pod healthy (`pod-health.sh`). Clean tmp dir.

**Steps:**
1. Create `/tmp/adhoc-seq.puml` containing `@startuml\nA -> B: hi\n@enduml`.
2. Run `scripts/render.sh /tmp/adhoc-seq.puml --type plantuml --out /tmp`.

**Verify:**
- `/tmp/adhoc-seq.light.svg` and `/tmp/adhoc-seq.dark.svg` both exist, >0 bytes.
- Both open in an SVG viewer without errors.
- Dark variant has `#2B2B2B` background where light has `#F7F7F7`.

## Scenario 2 — Embed in session log

**Precondition:** Scenario 1 output exists. Empty `~/Documents/Obsidian Vault/FDLE-Pipeline/sessions/_test.md` created with `# Test`.

**Steps:**
1. `scripts/embed-in-md.sh ~/.../sessions/_test.md adhoc-seq --caption "Sequence test"`.
2. `scripts/embed-in-md.sh ~/.../sessions/_test.md adhoc-seq --caption "Sequence test"` (second call).

**Verify:**
- `_test.md` has exactly one `[[adhoc-seq.light.svg]]` wikilink (idempotent).
- `_test.md` contains `## Diagrams` section with the `<div class="kroki-dual">` block.
- Blank lines appear *inside* the `<div>` before and after the wikilinks (CommonMark HTML-block rule).
- Caption `*Figure -- Sequence test*` appears below the embed.

## Scenario 3 — Session-end bookend (Plan 5 stub — document only)

**Precondition:** N/A — Plan 5 blocked.

**Steps:** Skip. Document the dependency.

**Verify:** `kroki-session` skill is absent from the skill list. Scenario will be
unlocked once Plan 5 ships.

## Scenario 4 — Pod-down recovery

**Precondition:** Pod running.

**Steps:**
1. `cd ~/kroki && podman compose stop kroki`.
2. Invoke any render: `scripts/render.sh /tmp/adhoc-seq.puml --type plantuml --out /tmp`.
3. Bring pod back: `cd ~/kroki && podman compose start kroki`.
4. Re-run the render.

**Verify:**
- Step 2 exits non-zero with a pod-health diagnostic.
- Step 4 succeeds once pod is back.
- No orphan `.tmp` files in `/tmp` (the SIGINT trap from Task 15 cleans them).

## Scenario 5 — Syntax error recovery

**Precondition:** Pod healthy.

**Steps:**
1. `echo "not a diagram" > /tmp/broken.puml`.
2. `scripts/render.sh /tmp/broken.puml --type plantuml --out /tmp`.

**Verify:**
- Exits with code 2.
- Stderr contains Kroki's 400-family diagnostic.
- `/tmp/broken.light.svg` and `/tmp/broken.dark.svg` do NOT exist (no partial artifacts).

## Scenario 6 — Dual-render theme switching (LIVE in Obsidian)

**THIS IS THE CRITICAL SCENARIO — catches b33d1af-class bugs.**

**Precondition:**
- CSS snippet installed via `install.sh` and toggled ON in Obsidian Settings → Appearance → CSS snippets.
- A note in the vault with a dual-render embed (e.g. `~/Documents/Obsidian Vault/Kroki-Plugin/theme-test/README.md` — this is preserved Plan 3 live-test content).

**Steps:**
1. Open Obsidian.
2. Navigate to the note with the embed.
3. With **Light** theme active: confirm only the light SVG renders (dark is hidden).
4. Switch to **Dark** theme (Ctrl+P → "Switch between light and dark mode").
5. Confirm only the dark SVG renders now (light is hidden).
6. Toggle back to light, confirm again.

**Verify:**
- Exactly one SVG is visible at any time.
- No flash of both SVGs during theme toggle.
- Wikilinks are rendered as images, not literal `![[...]]` text (CommonMark blank-line rule).

**If this fails:** inspect Obsidian's DOM with F12 / dev tools. Check whether
`[src$=".light.svg"]` / `[src$=".dark.svg"]` selectors match the `<span class="internal-embed">` elements. See `styles/kroki-theme.css` + commit
`b33d1af` for background.

## Scenario 7 — Native vs stitch legend

**Precondition:** Pod healthy.

**Steps:**
1. Create `/tmp/leg-plant.puml`:
   ```
   @startuml
   !include <C4/C4_Container>
   LEGEND()
   Container(a, "A", "", "core")
   @enduml
   ```
2. `scripts/render-with-legend.sh /tmp/leg-plant.puml --type c4plantuml --out /tmp`.
3. Create `/tmp/leg-mermaid.mmd`:
   ```
   graph LR
     A-->B
   ```
4. `scripts/render-with-legend.sh /tmp/leg-mermaid.mmd --type mermaid --out /tmp`.

**Verify:**
- `/tmp/leg-plant.light.svg` contains PlantUML's native legend box.
- `/tmp/leg-mermaid.light.svg` has the Kroki-plugin-composed legend stitched *below* the mermaid graph (taller than a plain mermaid render).

## Scenario 8 — Graceful degradation (legend fail)

**Precondition:** Pod healthy.

**Steps:**
1. Temporarily corrupt `styles/palette.yml` (e.g. insert `@@@` on line 1).
2. `scripts/render-with-legend.sh /tmp/adhoc-seq.puml --type plantuml --out /tmp`.
3. Restore `styles/palette.yml`.

**Verify:**
- The base dual-renders (`.light.svg`, `.dark.svg`) still exist and open correctly.
- Legend composition failure is logged to stderr but does not block the render.
- Exit code is 0 or 2 (acceptable — legend is optional). Design §13: "Legend composition fails — Degrade gracefully: save diagram without legend."

## Pass criteria

All scenarios except #3 must PASS before tagging a release. #3 stays marked
as blocked pending Plan 5.
