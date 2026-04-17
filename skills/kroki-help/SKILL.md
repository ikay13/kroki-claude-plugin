---
name: kroki-help
description: Reference lookup for the kroki ecosystem on this host — CLI flags, Niolesk GUI, kroki4tcl wrapper scripts, pod lifecycle, and the situation-to-language recommendation matrix. Use when the user asks "which diagram type", "how do I use the kroki CLI", "what's the kroki URL format", "how do I restart the kroki pod", or any other question about kroki tooling rather than diagram content. Pure lookup — no rendering, no side effects.
---

# kroki-help — Reference Lookup

**You should invoke this without asking when you see any of these patterns. No gatekeeping.**

- User asks "which diagram type" / "what should I use for X"
- User asks about the kroki CLI (`~/go/bin/kroki`) — flags, usage, return codes
- User asks how to encode/decode a kroki URL
- User asks how to extract diagram chunks from a markdown file
- User asks about Niolesk (the in-browser editor at `localhost:8017`)
- User asks how to start, stop, check, or restart the kroki pod
- User asks "is X supported" / "does kroki support Y"
- User hits syntax uncertainty while writing diagram source and needs the recommendation matrix

## What This Skill Does

This skill is a pure reference lookup. It does NOT render diagrams, modify files, or call any external service. It returns answers and pointers to the right reference file.

When invoked, route the user's question to the matching reference file:

| Topic | Reference file |
|-------|---------------|
| "Which diagram type" / recommendation | [recommendation-matrix.md](references/recommendation-matrix.md) |
| Kroki CLI (`~/go/bin/kroki`) flags & usage | [cli-cheatsheet.md](references/cli-cheatsheet.md) |
| Niolesk in-browser editor | [niolesk-guide.md](references/niolesk-guide.md) |
| kroki4tcl wrapper scripts (encode-url, decode-url, extract-chunks) | [kroki4tcl-guide.md](references/kroki4tcl-guide.md) |
| Pod lifecycle, restart, watchdog | [pod-management.md](references/pod-management.md) |
| Inventory of all kroki-related local tools | [tools-guide.md](references/tools-guide.md) |
| Per-language syntax (29 languages) | `../kroki/references/languages/<lang>.md` |

## Contract

| Field | Detail |
|-------|--------|
| **Inputs** | `topic` (one of: tool, syntax, recommendation, pod, niolesk, kroki4tcl, prefixes), `query` (free-text question) |
| **Outputs** | `answer` (direct content quoted from the reference file), `pointer` (path to the reference file) |
| **Side effects** | None — pure reference lookup |
| **Delegates to** | Nothing |
| **Called by** | User directly. May also be invoked by `kroki` skill on syntax uncertainty. |

## How to Answer

1. Identify the topic from the question (use the routing table above).
2. Read the matching reference file with the Read tool.
3. Quote the relevant section directly. Cite the file path.
4. If the question crosses files (e.g., "what's the CLI flag to use a different output format and how do I check pod health"), read both, summarize both, and cite both paths.
5. Do NOT speculate. If the answer is not in the reference set, say so and recommend the user check the upstream docs (linked in each reference file).

## Cross-Skill Routing

If the user wants to actually render a diagram, hand off to the `kroki` skill — do not attempt to render from this skill. If the user wants to embed a diagram in Obsidian, hand off to `kroki-obsidian` (Plan 3, not yet shipped).
