# Kroki Claude Code Plugin

A multi-skill Claude Code plugin for diagram generation, rendering, and embedding using a self-hosted Kroki server.

## Skills

| Skill | Purpose |
|-------|---------|
| `kroki` | Core rendering — generates diagram source, renders via Kroki, returns file path |
| `kroki-obsidian` | Obsidian vault integration — embeds diagrams in .md files (Plan 3) |
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
