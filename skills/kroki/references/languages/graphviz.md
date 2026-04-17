# Graphviz Reference

Graphviz excels at directed graphs, dependency trees, and layer diagrams. Its DOT language is concise and the layout engines (dot, neato, fdp, sfdp, circo, twopi) handle complex topologies automatically.

**Engine:** Core gateway (no companion container needed)
**File extensions:** `.dot`, `.gv`
**Kroki type string:** `graphviz`

## Directed Graph

```dot
digraph {
    rankdir=TB
    node [shape=box, style=filled, fillcolor="#E8F4FD"]
    edge [color="#808080"]

    A [label="Input Layer"]
    B [label="Processing"]
    C [label="Output Layer"]
    A -> B -> C
}
```

## Dependency Graph

```dot
digraph dependencies {
    rankdir=LR
    node [shape=component]

    auth [label="Auth Service"]
    api [label="API Gateway"]
    db [label="Database" shape=cylinder]
    cache [label="Redis Cache" shape=cylinder]

    api -> auth
    api -> db
    api -> cache
    auth -> db
}
```

## Layered Architecture

```dot
digraph layers {
    rankdir=TB
    node [shape=box, style=filled, width=3]
    edge [style=invis]

    subgraph cluster_0 {
        label="Presentation"
        style=filled
        fillcolor="#E8F4FD"
        ui [label="UI Components"]
    }
    subgraph cluster_1 {
        label="Business Logic"
        style=filled
        fillcolor="#B8DCF5"
        logic [label="Domain Services"]
    }
    subgraph cluster_2 {
        label="Data"
        style=filled
        fillcolor="#6BAFE0"
        data [label="Repositories"]
    }

    ui -> logic -> data
}
```

## Legend Support

**Native for simple legends** (subgraph cluster with label). **Stitch for complex legends** with multiple sections.

```dot
subgraph cluster_legend {
    label="Legend"
    style=filled
    fillcolor=white
    node [shape=plaintext]
    l1 [label="Blue = Core"]
    l2 [label="Gray = External"]
}
```

## Common Pitfalls

- Missing `digraph` keyword (bare `{ a -> b }` is invalid)
- `rankdir=LR` vs `rankdir=TB` changes layout dramatically — pick deliberately
- HTML-like labels (`<table>`) must be wrapped in `<` `>` not quotes
- `subgraph` name MUST start with `cluster_` to get a bounding box
- Semicolons are optional but help readability in complex graphs

## Upstream Docs

- https://graphviz.org/documentation/
- https://graphviz.org/doc/info/lang.html (DOT language)
- https://graphviz.org/doc/info/attrs.html (attributes)
