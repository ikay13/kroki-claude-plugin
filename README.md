# Kroki Claude Code Plugin

A multi-skill Claude Code plugin for diagram generation, rendering, and embedding using a self-hosted Kroki server.

## Skills

| Skill | Purpose |
|-------|---------|
| `kroki` | Core rendering — generates diagram source, renders via Kroki, returns file path |
| `kroki-obsidian` | Obsidian vault integration — embeds dual-theme diagrams, maintains `diagrams/INDEX.md`, manages vault symlink and CSS snippet |
| `kroki-session` | Session bookend automation — surfaces/refreshes diagrams (Plan 5) |
| `kroki-help` | Reference — syntax, tools, recommendation matrix (Plan 4) |

## Requirements

- Kroki server running at localhost:8000 (via `~/kroki/kroki.sh up`)
- Kroki CLI at `~/go/bin/kroki`
- Podman (rootless) for container management

## Quick Start

1. Register plugin: `claude plugin add ~/kroki-claude-plugin/`
2. Start Kroki: `~/kroki/kroki.sh up`
3. Ask Claude: "Draw a sequence diagram of user authentication"

## Obsidian Theme Install (optional, one-time)

Enable dual-theme diagram rendering in Obsidian:

1. Run: `~/kroki-claude-plugin/scripts/install-vault-theme.sh ~/Documents/Obsidian\ Vault`
2. In Obsidian: **Settings → Appearance → CSS snippets** → toggle `kroki-theme` on.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/render.sh`              | Base renderer — dual light/dark SVG output via Kroki CLI |
| `scripts/render-with-legend.sh`  | Render + compose + stitch legend below |
| `scripts/a11y-check.sh`          | Advisory WCAG + palette + grayscale validator |
| `scripts/flatten.sh`             | CSS-var SVG → hardcoded hex |
| `scripts/validate-references.sh` | Render reference snippets (regression check) |
| `scripts/embed-in-md.sh`         | Idempotent dual-wikilink block insert in a Markdown file |
| `scripts/update-index.sh`        | Regenerate `diagrams/INDEX.md` grouped by filename prefix |
| `scripts/ensure-symlink.sh`      | Create vault `diagrams/` symlink safely |
| `scripts/install-vault-theme.sh` | Copy `kroki-theme.css` into vault snippets dir |
| `scripts/install.sh`             | Unified idempotent installer (orchestrates the above) |
| `scripts/pod-health.sh`          | Verify Kroki gateway is reachable and healthy |
| `scripts/encode-url.sh`          | kroki4tcl URL encoder |
| `scripts/decode-url.sh`          | kroki4tcl URL decoder |
| `scripts/extract-chunks.sh`      | kroki4tcl chunk extraction helper |
| `tests/smoke.sh`                 | 29-fixture smoke + pytest + Obsidian integration check |
| `tests/verify-install.sh`        | 7-check install validator |

## Installation

Run the unified installer:

```bash
scripts/install.sh
```

This:
1. Installs `kroki-theme.css` into your vault's `.obsidian/snippets/` directory
2. Appends a kroki extension block to `~/.claude/rules/session-continuity.md` inside its `## Extension point: installer-appended instructions` section (if missing). Requires session-continuity.md with the Extension point section (Knowledge-Architecture v1 schema or later).
3. Creates `~/.kroki-plugin/` state directory
4. Installs systemd user timers (if systemd available)
5. Runs a quick smoke test

Override paths with `--vault-root PATH`, `--rules-file PATH`, `--state-dir PATH`.
Skip steps with `--skip-systemd` or `--skip-smoke`.

Verify the install:

```bash
tests/verify-install.sh
```

Runs 7 checks and reports pass/fail per check.

Flags (`--skip-systemd`, `--skip-pod`, `--skip-smoke`) are **not inherited** from `install.sh`. If you ran `install.sh --skip-systemd`, pass the same flag to `verify-install.sh` or the timer check will report a false FAIL.

## Style system

Machine-readable YAML style files in `styles/`:

- `palette.yml` — Okabe-Ito colorblind-safe palette
- `palettes/nature.yml`, `palettes/ieee.yml` — journal overrides
- `symbols.yml` — glyph vocabulary
- `abbreviations.yml` — acronym expansions
- `legend-template.yml` — placement + section layout
- `css-var-mapping.yml` — CSS var → fallback hex

Each is paired with a Markdown explainer (`.md`) describing rationale.

Consumed by `render-with-legend.sh`, `a11y-check.sh`, and `flatten.sh`.
