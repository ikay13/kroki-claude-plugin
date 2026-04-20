---
name: kroki-session
description: Session bookend automation for projects using the kroki plugin. Invokes mode=start (read-only diagram inventory surface) at session start and mode=end (render changes + embed in session log + update memory + milestone snapshots) at session end. Use when user says "snapshot the session", "bookend", "wrap up", "milestone diagram", or when session-continuity workflow fires via the INSTALLER block in session-continuity.md. Delegates rendering to the kroki skill and embedding to the kroki-obsidian skill.
---

# kroki-session — Session Bookend Automation

**You should invoke this without asking when you see any of these patterns. No gatekeeping.**

- User says "snapshot the session", "bookend", "wrap up diagrams", "milestone diagram"
- session-continuity.md end-of-session sequence fires — the INSTALLER block tells you to invoke `scripts/session-end.sh --auto --project <X>`
- User explicitly names a milestone label: "snapshot as release-alpha" → pass `--milestone-label release-alpha`
- git tag matching `v*` (semver) was placed on HEAD during this session → mode=end auto-detects

## What This Skill Does

Three modes, three bash entrypoints:

| Mode | Entrypoint | When | What it does |
|---|---|---|---|
| start | `scripts/session-start.sh` | Session start | Read-only. Surfaces prior-session diagram inventory + INDEX.md references + memory's last next-steps. Emits JSON payload on stdout. |
| end | `scripts/session-end.sh` | Session end | Renders modified diagrams, regenerates INDEX.md, embeds dual-theme wikilinks in session log's `## diagrams` section, updates memory `## touched-diagrams`, auto-snapshots any new `v*` tag on HEAD. |
| snapshot | `scripts/session-snapshot.sh` | Milestone (auto or explicit) | All-or-nothing dual-theme composite SVG of all diagrams. Writes `diagrams/milestones/<label>.{light,dark}.svg` + audit trail `<label>.source-list.txt`. |

## Auto-invoke suppression

Set `KROKI_SESSION_AUTO=0` to disable INSTALLER-driven auto-invocations. The env var only affects `--auto`-flagged calls. Explicit trigger-phrase invocations always run.

## Contract

| Field | Detail |
|---|---|
| **Inputs** | `--project <name>` (required), `--auto` (for INSTALLER path), `--milestone-label <label>` (end/snapshot only), `--vault-path <path>` (override convention) |
| **Outputs** | start: JSON payload on stdout (schema in references/bookend-workflow.md). end: summary payload on stderr. snapshot: composite SVGs + INDEX.md row. |
| **Side effects** | start: none (read-only). end: git-diff detection, render + embed + INDEX regen + memory update + milestone snapshot. snapshot: writes composite SVGs + audit trail. |
| **Delegates to** | `render.sh`, `embed-in-md.sh`, `update-index.sh`, `a11y-check.sh`, `pod-health.sh`, `lib/kroki_util.stitch_svgs_vertical` |
| **Called by** | User (trigger phrases) + Claude (via `<!-- INSTALLER: kroki-session -->` block in `session-continuity.md`) |

## Exit codes (mode=end)

- `0` — success (≥1 diagram rendered, OR no changes/milestone to capture)
- `1` — all render/embed attempts failed (indicates per-diagram bugs or embed-pipeline failure)
- `2` — environmental failure (pod unrecoverable, git not installed)

## References

| Topic | File |
|---|---|
| mode=start / mode=end / milestone workflows | [bookend-workflow.md](references/bookend-workflow.md) |
| Git diff + activity gate + `v*` semver detection | [snapshot-detection.md](references/snapshot-detection.md) |
| `## diagrams` in session log, `## touched-diagrams` in memory, INSTALLER block | [integration-with-rules.md](references/integration-with-rules.md) |

## Environment

- Plugin root: `~/kroki-claude-plugin/`
- Vault root: `~/Documents/Obsidian Vault/<Project>/` (per obsidian-project-sync.md)
- Memory: `~/.claude/projects/-home-orin/memory/project_<snake>.md` (per memory-schema.md)
- State dir: `~/.kroki-plugin/` (a11y reports, errors.log)

## v2 extension point

`policies/` directory is empty in v1. v2 will populate it with SEBoK-derived rules for recommending diagram types by domain × role × phase.
