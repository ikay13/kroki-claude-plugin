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

## Scenario 9 — mode=start surfaces prior session's diagrams

**Prereqs:** A project with diagrams + at least one prior session log containing a `## diagrams` section.

1. `cd ~/kroki-claude-plugin`
2. Run: `./scripts/session-start.sh --project Kroki-Plugin`
3. Inspect stdout: should be a JSON object with keys `mode`, `project`, `vault_dir`, `loaded_diagrams`, `reference_summary`, `last_next_steps`.
4. Inspect stderr: one line "kroki-session: surfaced N prior diagrams + M references".

**Pass:** JSON validates, values reflect prior session content.

---

## Scenario 10 — mode=end with 3 modified sources

**Prereqs:** Clean working tree in a kroki project. Pod running.

1. Edit 3 diagram sources: e.g., modify `diagrams/seq-kroki-render-flow.puml`, add a new source `diagrams/trace-smoke.puml`, delete one.
2. Create/ensure today's session log exists: `touch "$HOME/Documents/Obsidian Vault/Kroki-Plugin/sessions/$(date +%Y-%m-%d)-Kroki-Plugin-session-99.md"` with minimal schema-compliant content.
3. Run: `./scripts/session-end.sh --project Kroki-Plugin`
4. Inspect stderr summary: should report `rendered: 2/2`, `embeds: 2 added`, `milestone: none`, `exit: 0`.
5. Open the session log in Obsidian: `## diagrams` section present with two dual-wikilink blocks.
6. INDEX.md regenerated.

**Pass:** both renders succeed, embed is idempotent (re-run produces no duplicates), INDEX.md reflects current state.

---

## Scenario 11 — mode=end with pod down

**Prereqs:** Pod stopped. `cd ~/kroki/ && ./kroki.sh down`.

1. Modify a diagram source.
2. Run: `./scripts/session-end.sh --project Kroki-Plugin`
3. Expected stderr: `kroki-session: pod preflight failed (rc=N); ...`
4. Expected exit code: `2`.

**Pass:** no spurious renders attempted, exit 2, clear environmental error message.

---

## Scenario 12 — Milestone auto-detect on `v1.0.0` tag

**Prereqs:** Clean working tree.

1. `git tag v1.0.0-test` (temporary; delete after)
2. Run: `./scripts/session-end.sh --project Kroki-Plugin`
3. Inspect summary: `milestone: "v1.0.0-test" (auto-detect, snapshot generated)`.
4. Inspect `diagrams/milestones/`: `v1.0.0-test.light.svg`, `v1.0.0-test.dark.svg`, `v1.0.0-test.source-list.txt` exist.
5. Re-run: second invocation should NOT regenerate (existence check skips).
6. Create `diagrams/milestones/v1.0.0-test.skip`, delete the .svg files, re-run: should skip due to sentinel.
7. `git tag -d v1.0.0-test` (cleanup).

**Pass:** auto-detect fires once, sentinel suppresses, existence check prevents duplication.

---

## Scenario 13 — Activity gate + env var skip

1. Export `KROKI_SESSION_AUTO=0` in shell.
2. Run: `./scripts/session-start.sh --auto --project Kroki-Plugin`
3. Expected: silent (no stdout, no stderr), exit 0.
4. Run: `./scripts/session-start.sh --project Kroki-Plugin` (no --auto)
5. Expected: proceeds normally (env var ignored).
6. Unset: `unset KROKI_SESSION_AUTO`.

**Pass:** --auto honors env var; explicit invocation ignores it.

---

## Scenario 14 — Session log missing at mode=end

**Prereqs:** Project with diagrams, but no session log for today in `sessions/`.

1. Modify a diagram source.
2. Run: `./scripts/session-end.sh --project Kroki-Plugin`
3. Inspect stderr: should contain "no session log found at mode=end — embed skipped. Ensure session-continuity workflow creates the log before kroki-session fires, then re-invoke."
4. Inspect summary: `embeds: skipped (no session log present)`.
5. No stub file created in `sessions/`.
6. INDEX.md still regenerated.

**Pass:** render + INDEX + memory update all proceed; embed step no-op; no stub.

---

## Scenario 15 — Migration from v0.9.0 `INSTALLER: kroki` marker

**Prereqs:** Start from a `session-continuity.md` that has the old `<!-- INSTALLER: kroki -->` block but not the new `kroki-session` block.

1. Copy `session-continuity.md` to a backup: `cp ~/.claude/rules/session-continuity.md /tmp/continuity.bak.md`.
2. If already migrated, simulate the old state: `sed -i '/<!-- INSTALLER: kroki-session -->/,/<!-- \/INSTALLER: kroki-session -->/d' ~/.claude/rules/session-continuity.md && printf '\n<!-- INSTALLER: kroki -->\nlegacy placeholder\n<!-- /INSTALLER: kroki -->\n' >> ~/.claude/rules/session-continuity.md`.
3. Run: `./scripts/install.sh` (full install).
4. Verify: `grep -c "INSTALLER: kroki-session" ~/.claude/rules/session-continuity.md` → 2 (open + close).
5. Verify: old marker removed: `grep "INSTALLER: kroki " ~/.claude/rules/session-continuity.md` → no output.
6. Restore: `cp /tmp/continuity.bak.md ~/.claude/rules/session-continuity.md`.

**Pass:** new marker present, old marker absent, no duplicate blocks.

---

## Scenario 16 — Editor-lock happy path (Plan 5c)

**Prerequisites:** kroki pod running, Niolesk accessible at `http://localhost:8017`, a local browser available.

**Steps:**

1. Choose a real `.puml` file in your diagrams directory, e.g. `diagrams/arch-foo.puml`.
2. Open it via: `scripts/editor-open.sh diagrams/arch-foo.puml`
   Expect: Niolesk opens in your browser with the source pre-loaded; terminal prints a usage reminder; `~/.kroki-plugin/.active-editor.lock` exists with `source_path` set to the realpath of `diagrams/arch-foo.puml`.
3. Make a visible edit in Niolesk (change an arrow label, add a participant).
4. Click **Download** in Niolesk — the file saves to `~/Downloads/arch-foo.puml`.
5. Move it back: `mv ~/Downloads/arch-foo.puml diagrams/arch-foo.puml`
6. Close: `scripts/editor-close.sh`
   Expect: terminal prints "Lock released." plus the save-back reminder; `~/.kroki-plugin/.active-editor.lock` is gone.
7. Verify the source file contains your edit.

**Pass criteria:** lock appeared and cleared; Niolesk pre-loaded correctly; file contains the edit you made.

---

## Scenario 17 — Render blocks during edit (Plan 5c)

**Prerequisites:** kroki pod running.

**Steps:**

1. In terminal A: `scripts/editor-open.sh diagrams/arch-foo.puml`
2. In terminal B: `scripts/render.sh diagrams/arch-foo.puml`
   Expect: exit code 2; stderr mentions "editor lock active" and "`editor-close.sh`"; no new `.svg` file written.
3. In terminal B, try a DIFFERENT source: `scripts/render.sh diagrams/arch-bar.puml`
   Expect: exit 0; output `.svg` is written normally (the lock doesn't block other files).
4. In terminal A: `scripts/editor-close.sh`
5. In terminal B, retry: `scripts/render.sh diagrams/arch-foo.puml`
   Expect: exit 0; output `.svg` is written.

**Pass criteria:** step 2 exits 2 with guidance; step 3 succeeds; step 5 succeeds after close.

## Pass criteria

All scenarios except #3 must PASS before tagging a release. #3 stays marked
as blocked pending Plan 5.
