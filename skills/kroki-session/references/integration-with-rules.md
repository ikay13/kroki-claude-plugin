# Integration with `~/.claude/rules/` schemas

## session-log-schema.md

kroki-session writes to a new `## diagrams` conditional section, added to the schema as part of Plan 5a:

| Section header | Requirement | Notes |
|---|---|---|
| `## diagrams` | Conditional | Written by `kroki-session(mode=end)`. Dual-theme `<div class="kroki-dual">` wikilink blocks + captions. Idempotent — re-runs replace section content. |

Schema change lands once (not per-install); install.sh does not touch the schema file.

## memory-schema.md

kroki-session reads and writes `## touched-diagrams` in `project_<snake>.md` memory files. Schema already declares this as an unbounded list. mode=end dedupe-merges: `sorted(set(existing + new_successes))`.

## session-continuity.md — INSTALLER block

Plan 5a installs this marker-bracketed block:

```markdown
<!-- INSTALLER: kroki-session -->
## Kroki session bookends

If the current session involves a project with a `diagrams/` directory in its vault folder:

**At session start** (after reading memory per §"At the start of every session"):
Invoke `~/kroki-claude-plugin/scripts/session-start.sh --auto --project <project>`. Use the returned JSON payload (on stdout) to surface prior diagram inventory to the user.

**At session end** (after steps 1–4 of end-of-session sequence, before generating the resume prompt):
Invoke `~/kroki-claude-plugin/scripts/session-end.sh --auto --project <project>`. If a `v*` semver tag was placed on HEAD during this session and no milestone snapshot exists, auto-capture it. If the user named a milestone explicitly during the session (e.g., "snapshot as release-alpha"), pass `--milestone-label <label>` instead — and omit `--auto` so it is treated as an explicit invocation. Report the summary payload (stderr) in the session's close-out.

For multi-project sessions: run mode=end once per project touched, serially.

**Auto-invoke suppression:** both start and end auto-invocations respect `KROKI_SESSION_AUTO=0` — when the environment variable is set, the `--auto`-flagged invocations exit silently. Explicit user-triggered invocations (without `--auto`) run regardless of the env var.
<!-- /INSTALLER: kroki-session -->
```

Installation detects and migrates from the v0.9.0 `<!-- INSTALLER: kroki -->` marker (see `scripts/install.sh` Step 2).

Uninstall: `install.sh --uninstall` strips the marker block by `sed`. Schema row in `session-log-schema.md` is NOT removed (persistent by convention).

## obsidian-project-sync.md

kroki-session's `vault_paths(project)` honors the convention `~/Documents/Obsidian Vault/<Project>/`. Hardcoded fallback list is intentionally **not** used — rule violations should surface, not get papered over. Override: `--vault-path /path/to/folder` bypasses convention for one invocation.
