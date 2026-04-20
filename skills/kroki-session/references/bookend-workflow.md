# Bookend Workflow — detailed mode=start / mode=end / milestone flow

## mode=start — read-only inventory surface

Invoked at session start (via INSTALLER block or trigger phrase).

1. Env-var gate: if `--auto` AND `KROKI_SESSION_AUTO=0`, exit silent.
2. Resolve vault path (convention or `--vault-path` override).
3. Activity gate — skip if (a) no `diagrams/` dir OR (b) no prior diagram activity in memory AND no prior `## diagrams` in previous session log.
4. Read `diagrams/INDEX.md` → `reference_summary`.
5. Parse previous session log's `## diagrams` → `loaded_diagrams`.
6. Read memory `## next-steps` → `last_next_steps`.
7. Emit JSON payload on stdout; brief summary on stderr.

### JSON payload schema (stdout)

```python
class ReferenceEntry(TypedDict):
    basename: str       # e.g. "arch-overview"
    purpose: str        # first-comment purpose, ≤120 chars
    last_updated: str   # YYYY-MM-DD from INDEX.md row

class StartPayload(TypedDict):
    mode: Literal["start"]
    project: str
    vault_dir: str
    loaded_diagrams: list[str]           # basenames from prev session log ## diagrams
    reference_summary: list[ReferenceEntry]
    last_next_steps: list[str]           # from memory ## next-steps
```

All fields always present. Empty lists when no data.

## mode=end — session-end snapshot

Invoked at session end, after `session-continuity.md` steps 1–4 (memory + tracker + session log + handoff writes).

Steps (spec §6.2):

0. Env-var gate (`--auto` + `KROKI_SESSION_AUTO=0` → exit silent)
1. Pod preflight (`scripts/pod-health.sh`) — exit 2 on unrecoverable
2. Resolve vault path
3. Git state check — skip gracefully on DETACHED / MERGE / NO_REPO; exit 2 on NO_GIT
4. Detect changes (modified/new/deleted) in `<vault>/diagrams/`
5. Milestone pre-check — `git tag --points-at HEAD --list 'v*'` intersected with "no existing `<tag>.light.svg` and no `<tag>.skip` sentinel"
6. Early exit if no changes AND no milestone
7. Per-diagram render loop (render.sh + a11y-check.sh; try/except + continue on per-diagram failures)
8. Log deleted file names (preserve render artifacts)
9. `update-index.sh` regenerates `INDEX.md`
10. Resolve current session log; if missing → skip embed with stderr note (don't create stub)
11. Embed loop: `embed-in-md.sh ... --section "## diagrams" --caption <purpose>` per success
12. Milestone handling: delegate to `session-snapshot.sh` if label set
13. Memory update: `## touched-diagrams` extended with successful basenames, deduped + sorted
14. Summary payload on stderr

Exit codes:
- `0` — ≥1 success OR no changes (nothing to do is valid)
- `1` — changes existed AND all attempts failed
- `2` — environmental failure

## mode=snapshot — milestone composite

All-or-nothing. Renders all diagrams dual-theme, stitches two composites (light + dark), writes audit trail + INDEX.md row.

Called either:
- By user explicitly: `session-snapshot.sh --project <P> --milestone-label <L>`
- By end.py Step 12 when `--milestone-label` is set or a `v*` tag is auto-detected
