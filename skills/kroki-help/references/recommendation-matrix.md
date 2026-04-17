# Recommendation Matrix — Situation → Diagram Language

Source of truth for "which diagram type should I use for X?" Mirrors §10 of `~/Documents/Obsidian Vault/Kroki-Plugin/specs/2026-04-17-kroki-plugin-design.md`.

## Quick matrix

| # | Situation | Default | Kroki type | Reason |
|---|-----------|---------|-----------|--------|
| 1 | Architecture / system overview | C4-PlantUML | `c4plantuml` | Industry standard for C4 views, native `LEGEND()` |
| 1b | Dependency / layer graphs | Graphviz (dot) | `graphviz` | Best at directed graphs and dependency trees |
| 2 | Sequence / interaction / async | PlantUML | `plantuml` | Best in class for lifelines, async, alt/loop |
| 3 | Flowchart / decision logic | Mermaid | `mermaid` | Widely readable, Obsidian renders natively |
| 4a | Database schema | DBML | `dbml` | Clean DB-oriented output |
| 4b | Conceptual entity relationships | Mermaid ER | `mermaid` (ER subset) | Clean for conceptual entities |
| 5 | Network / infrastructure topology | NwDiag | `nwdiag` | Purpose-built; siblings PacketDiag, RackDiag |
| 6 | Quick sketch / whiteboard feel | Excalidraw | `excalidraw` | Hand-drawn aesthetic |
| 7 | VHDL / hardware entity symbols | Symbolator | `symbolator` | Only Kroki engine for VHDL entity symbols |
| 8 | State machine | PlantUML | `plantuml` | Hierarchical states, entry/exit actions, parallel regions |
| 9 | PM (Gantt / WBS / Precedence) | PlantUML | `plantuml` (gantt/wbs/precedence) | Native Gantt + WBS overlay capability |
| 10 | UML class diagram | PlantUML | `plantuml` | De facto standard |
| 11 | Use case diagram | PlantUML | `plantuml` | Standard UML |
| 12 | Timing / digital signals | WaveDrom | `wavedrom` | Purpose-built for waveforms |
| 13 | Byte layout / packet structure | ByteField or PacketDiag | `bytefield` / `packetdiag` | Byte-accurate visualization |
| 14 | Systems thinking — causal loops | Graphviz (dot) | `graphviz` | Directed graphs with feedback cycles |
| 15 | Mind map / idea map | PlantUML mindmap | `plantuml` (`@startmindmap`) | First-class mindmap syntax |
| 16 | BPMN business processes | BPMN | `bpmn` | Standard notation, runs on bpmn-js engine |
| 17 | ER (BurntSushi-style, terse) | erd | `erd` | Concise text-only ER syntax |
| 18 | Wire harness / cabling | WireViz | `wireviz` | Purpose-built for wire harness diagrams |
| 19 | Block diagram (generic blocks + arrows) | BlockDiag | `blockdiag` | Concise block-diagram DSL |
| 20 | Activity flow (lanes) | ActDiag | `actdiag` | BlockDiag-family lane-aware activity diagram |
| 21 | Sequence (BlockDiag-family, terse) | SeqDiag | `seqdiag` | Lighter-weight than PlantUML for short sequences |
| 22 | Architecture (modern syntax) | D2 | `d2` | Auto-layout, theming, clean syntax |
| 23 | Hand-drawn UML / lightweight class | Nomnoml | `nomnoml` | Concise UML-like text → SVG |
| 24 | ASCII-art layout in docs | Ditaa or Svgbob | `ditaa` / `svgbob` | Accept ASCII art, render to SVG |
| 25 | PIC-language flow / circuit-style | Pikchr | `pikchr` | PIC descendant, dense layouts |
| 26 | Charts / data viz (declarative) | Vega-Lite | `vegalite` | Concise grammar of graphics |
| 27 | Charts / data viz (full Vega) | Vega | `vega` | Full programmable visualization grammar |
| 28 | Architecture (Structurizr DSL) | Structurizr | `structurizr` | C4-aligned architecture-as-code |
| 29 | Imported drawio file | diagrams.net | `diagramsnet` | Render existing drawio XML |
| 30 | LaTeX / academic figures | TikZ | `tikz` | Math-typesetting integration |
| 31 | UMLet diagrams | UMLet | `umlet` | Simple UML, palette-driven |

## Decision flow

1. **Is the diagram an architecture overview?** → C4-PlantUML (#1) or D2 (#22) for modern.
2. **Is the diagram a sequence / interaction?** → PlantUML (#2) for full features, SeqDiag (#21) for terse.
3. **Is the diagram a decision flow / flowchart?** → Mermaid (#3) — also renders natively in Obsidian.
4. **Is the diagram for a database / data model?** → DBML (#4a), Mermaid ER (#4b), or erd (#17).
5. **Is the diagram a hardware / electrical artifact?** → Symbolator (#7) for VHDL, WaveDrom (#12) for timing, ByteField/PacketDiag (#13) for byte layout, WireViz (#18) for wire harness.
6. **Is the diagram a project artifact?** → PlantUML Gantt/WBS (#9).
7. **Is the diagram a chart of data?** → Vega-Lite (#26) for typical, Vega (#27) for advanced.
8. **Is the diagram a network / topology?** → NwDiag (#5).
9. **None of the above?** → Default to PlantUML (most versatile) or D2 (cleanest modern).

## Per-language deep dive

For syntax examples, common pitfalls, and legend support per language, see:

- `~/kroki-claude-plugin/skills/kroki/references/languages/<lang>.md` — one file per language

The `<lang>` matches the kroki type string in the table above.

## Future override layer

In v2, `~/kroki-claude-plugin/skills/kroki-session/policies/` will hold domain × role × phase rules that override this matrix (e.g. "in a NASA SE Phase B Architecture review, prefer SysML BDD over generic C4"). v1 has no policies — this matrix is the authority.
