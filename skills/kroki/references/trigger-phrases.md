# Trigger Phrases

Expandable list of phrases and patterns that should trigger the `kroki` skill.

## Core Triggers (explicit)

- "diagram this", "diagram the", "draw a diagram"
- "render a [type]", "render this as"
- "draw a [flowchart|sequence|class|state|...]"
- "visualize [the|this|my]"
- "create a [diagram|chart|graph|flowchart]"
- "show me the architecture"
- "map out [the|this]"

## Implicit Triggers (contextual)

Invoke `kroki` when:
- The user asks to *explain* a system, flow, architecture, or relationship where prose would require >3 paragraphs
- You are about to write a text description of a multi-step process that would be clearer as a flowchart
- The user mentions terms like "architecture", "pipeline", "workflow", "data flow", "dependency tree", "entity relationship"
- Code review reveals a complex interaction that would benefit from a sequence diagram

## Skill-Specific Triggers (route to other skills)

| Phrase | Routes to |
|--------|----------|
| "embed diagram", "add to tracker", "put in session log" | `kroki-obsidian` |
| "snapshot the session", "bookend", "milestone diagram" | `kroki-session` |
| "which diagram type", "kroki syntax for", "how do I use" | `kroki-help` |
