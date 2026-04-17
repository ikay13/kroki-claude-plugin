# C4-PlantUML Reference

C4-PlantUML implements the C4 model (Context, Container, Component, Code) for architecture diagrams. Industry standard for system architecture visualization. Has a native `LEGEND()` macro.

**Engine:** Core gateway (uses PlantUML engine with C4 library)
**File extensions:** `.puml` (same as PlantUML — distinguish by `!include <C4/...>`)
**Kroki type string:** `c4plantuml`

## Context Diagram (Level 1)

```plantuml
@startuml
!include <C4/C4_Context>

title System Context

Person(user, "User", "A human user of the system")
System(system, "My System", "Core application")
System_Ext(email, "Email Service", "Sends notifications")
System_Ext(payment, "Payment Gateway", "Processes payments")

Rel(user, system, "Uses", "HTTPS")
Rel(system, email, "Sends emails", "SMTP")
Rel(system, payment, "Processes payments", "HTTPS")

SHOW_LEGEND()
@enduml
```

## Container Diagram (Level 2)

```plantuml
@startuml
!include <C4/C4_Container>

title Container Diagram

Person(user, "User")

System_Boundary(sys, "My System") {
    Container(web, "Web App", "React", "Frontend SPA")
    Container(api, "API Server", "Python/FastAPI", "REST API")
    ContainerDb(db, "Database", "PostgreSQL", "Stores data")
    Container(worker, "Background Worker", "Celery", "Async processing")
}

Rel(user, web, "Uses", "HTTPS")
Rel(web, api, "Calls", "JSON/HTTPS")
Rel(api, db, "Reads/Writes", "SQL")
Rel(api, worker, "Enqueues", "Redis")

SHOW_LEGEND()
@enduml
```

## Component Diagram (Level 3)

```plantuml
@startuml
!include <C4/C4_Component>

title API Server Components

Container_Boundary(api, "API Server") {
    Component(auth, "Auth Module", "JWT", "Authentication")
    Component(routes, "Route Handler", "FastAPI", "HTTP routing")
    Component(service, "Business Logic", "Python", "Core domain")
    Component(repo, "Repository", "SQLAlchemy", "Data access")
}

Rel(routes, auth, "Validates tokens")
Rel(routes, service, "Delegates to")
Rel(service, repo, "Uses")

SHOW_LEGEND()
@enduml
```

## Legend Support

**Native.** C4-PlantUML has built-in `SHOW_LEGEND()` and `LEGEND()` macros that auto-generate relationship and element type legends.

```plantuml
SHOW_LEGEND()
' or for custom:
LEGEND()
```

## Common Pitfalls

- Use Kroki type `c4plantuml` not `plantuml` — the C4 includes won't resolve with plain PlantUML
- `System_Boundary` is for Level 2 (containers); `Container_Boundary` is for Level 3 (components) — mixing them produces confusing output
- `Rel()` arrows go from left to right by default; use `Rel_L`, `Rel_R`, `Rel_U`, `Rel_D` for direction
- `SHOW_LEGEND()` must come after all `Rel()` calls to capture all relationship types

## Upstream Docs

- https://github.com/plantuml-stdlib/C4-PlantUML
- https://c4model.com/ (C4 model specification)
