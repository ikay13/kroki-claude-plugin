---
name: kroki
description: Generate and render diagrams via local Kroki server. Supports 29 diagram languages (PlantUML, Mermaid, Graphviz, D2, C4, and more). Use when user says "diagram", "render", "draw", "visualize", "flowchart", or when a system/flow/architecture would be clearer as a diagram than prose. Also use when you determine a diagram would help explain something — no gatekeeping.
---

# Kroki — Core Rendering Skill

**You should invoke this without asking when you see any of these patterns. No gatekeeping.**

- User says "diagram", "render", "draw", "visualize", "flowchart", "chart", "graph"
- User asks to explain a system, flow, architecture, or relationship where prose would be verbose
- You determine a diagram would clarify your explanation
- User provides diagram source and wants it rendered

See [trigger-phrases.md](references/trigger-phrases.md) for the full expandable list.

## What This Skill Does

1. Generate diagram source code in the appropriate language
2. Render it via the local Kroki server (localhost:8000)
3. Save both the source file and rendered SVG to disk
4. Return the file path to the user

## How To Render

Use the rendering script at the plugin root:

```bash
~/kroki-claude-plugin/scripts/render.sh <source_file> [--type <type>] [--format <fmt>] [--out <dir>]
```

The script handles:
- Pod health check (auto-starts Kroki if not running)
- Atomic writes (temp file + mv — no corrupt outputs)
- Error surfacing (syntax errors, timeouts, empty output)

### Choosing the Diagram Language

See [references/languages/](references/languages/) for per-language syntax guides. For quick selection:

| Situation | Language | Kroki type |
|-----------|----------|-----------|
| Architecture / system overview | C4-PlantUML | `c4plantuml` |
| Dependency / layer graphs | Graphviz | `graphviz` |
| Sequence / interaction | PlantUML | `plantuml` |
| Flowchart / decision logic | Mermaid | `mermaid` |
| Modern architecture | D2 | `d2` |

Full recommendation matrix in `kroki-help/references/recommendation-matrix.md`.

### Source File Conventions

Every diagram source MUST start with a one-line comment describing its purpose:

```
' High-level 5-layer architecture overview       (PlantUML)
%% Task routing through PAUL to provider adapters (Mermaid)
# MSP and external agents context diagram         (D2)
// Dependency graph for Layer 3 adapters          (Graphviz)
```

This comment is parsed by `update-index.sh` to populate `diagrams/INDEX.md`.

### Naming Convention

Use SE/SW/PM-aligned prefixes. See [naming-prefixes.md](../../styles/naming-prefixes.md) for the full table.

Reference-category: `<prefix>-<project>-<topic>.<ext>` (e.g., `arch-msp-layer-stack.puml`)
Session-category: `YYYY-MM-DD-<project>-<prefix>-<topic>.<ext>` (e.g., `2026-04-17-MSP-bug-adapter-routing.puml`)

### Output Formats

See [output-formats.md](references/output-formats.md) for SVG vs PNG vs PDF guidance.

Default: SVG (text-based, scalable, Obsidian-embeddable, git-friendly).

## Contract

| Field | Detail |
|-------|--------|
| **Inputs** | source (string or file path), language, output_format (default svg), output_path (default $PWD) |
| **Outputs** | render_path, source_path, status (ok or error + diagnostic) |
| **Side effects** | Writes source + render to disk. Touches ~/.kroki-plugin/.last-use. Calls pod-health.sh on error. |
| **Delegates to** | Nothing — this is a leaf skill |
| **Called by** | User, kroki-obsidian, any other skill |

## Environment

- Kroki server: `localhost:8000` (Podman pod via `~/kroki/kroki.sh`)
- Kroki CLI: `~/go/bin/kroki`
- Pod management: `~/kroki/kroki.sh {up|down|status|logs}`
- Kroki config: `~/kroki.yml`
