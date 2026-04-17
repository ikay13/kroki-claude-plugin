# Mermaid Reference

Mermaid is widely readable and renders natively in Obsidian (without Kroki) as a fenced code block. Best for flowcharts and decision logic. Use Kroki rendering when you need file output (SVG/PNG) or legend stitching.

**Engine:** Companion container (`kroki-mermaid`)
**File extensions:** `.mmd`, `.mermaid`
**Kroki type string:** `mermaid`

## Flowchart

```mermaid
flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Process A]
    B -->|No| D[Process B]
    C --> E[End]
    D --> E
```

## Sequence Diagram

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant D as Database
    C->>S: POST /api/data
    S->>D: INSERT query
    D-->>S: OK
    S-->>C: 201 Created
```

## Entity-Relationship

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    PRODUCT ||--o{ LINE_ITEM : "is in"
    USER {
        string name
        string email
    }
    ORDER {
        int id
        decimal total
    }
```

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Running : start
    Running --> Idle : stop
    Running --> Error : crash
    Error --> Idle : reset
```

## Legend Support

**Stitch required.** Mermaid has no native legend syntax. Use the plugin's stitch mode — a separate legend SVG is composited alongside the diagram.

## Common Pitfalls

- `flowchart` (new) vs `graph` (deprecated) — always use `flowchart`
- Arrow syntax: `-->` (solid), `-.->` (dotted), `==>` (thick) — mistyped arrows silently parse as text
- Node IDs cannot start with a number or contain spaces without brackets
- `stateDiagram-v2` (use v2) vs `stateDiagram` (v1, fewer features)
- Obsidian renders mermaid natively in code fences — Kroki only needed for file output

## Upstream Docs

- https://mermaid.js.org/
- https://mermaid.js.org/syntax/flowchart.html
- https://mermaid.js.org/syntax/sequenceDiagram.html
- https://mermaid.js.org/syntax/entityRelationshipDiagram.html
