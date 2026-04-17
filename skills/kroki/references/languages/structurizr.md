# Structurizr DSL Reference

Structurizr is C4-architecture-as-code. The Structurizr DSL is purpose-built for the C4 model and produces context, container, component, and dynamic views from a single source.

**Engine:** Companion container (`kroki-structurizr`)
**File extensions:** `.dsl`
**Kroki type string:** `structurizr`

## Minimal context view

```structurizr
workspace {
  model {
    user = person "User"
    system = softwareSystem "My System" {
      web = container "Web App" "User-facing UI"
      api = container "API" "Backend service"
      db = container "Database" "Stores data"

      user -> web "Uses"
      web -> api "Calls" "JSON/HTTPS"
      api -> db "Reads/Writes" "SQL"
    }
  }
  views {
    systemContext system "ContextView" {
      include *
      autoLayout
    }
    container system "ContainerView" {
      include *
      autoLayout
    }
  }
}
```

## With styles and tags

```structurizr
workspace {
  model {
    user = person "User"
    system = softwareSystem "Order System" {
      web = container "Web Frontend" "" "" "Web Browser"
      api = container "API" "" "" "API"
      db = container "Database" "" "" "Database"

      user -> web "Browses"
      web -> api "JSON/HTTPS"
      api -> db "JDBC"
    }
  }
  views {
    container system "Containers" {
      include *
      autoLayout
    }
    styles {
      element "Web Browser" { background "#56B4E9" shape WebBrowser }
      element "API" { background "#0072B2" }
      element "Database" { background "#009E73" shape Cylinder }
    }
  }
}
```

## Legend Support

**Native.** Structurizr generates a legend automatically based on the styles defined in the views block.

## Common Pitfalls

- The `workspace { ... }` block is the outermost wrapper — required.
- Identifiers (`user`, `system`, etc.) are how you reference elements later — they must be unique within scope.
- `autoLayout` is needed unless you specify positions explicitly.
- Styles target tags applied to elements (the third `""` in `softwareSystem` / `container`).
- Don't put logic in the DSL — it's declarative; computations belong in your authoring tool.

## Upstream Docs

- https://docs.structurizr.com/dsl
- https://github.com/structurizr/dsl
