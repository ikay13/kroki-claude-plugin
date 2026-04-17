# PlantUML Reference

PlantUML is the most versatile Kroki language — supports sequence, class, state, activity, component, use case, object, deployment, timing, Gantt, WBS, mindmap, and JSON/YAML diagrams. It's the default choice for most UML and PM diagram types.

**Engine:** Core gateway (no companion container needed)
**File extensions:** `.puml`, `.plantuml`, `.pu`
**Kroki type string:** `plantuml`

## Sequence Diagram

```plantuml
@startuml
participant Alice
participant Bob
Alice -> Bob: Request
activate Bob
Bob --> Alice: Response
deactivate Bob
@enduml
```

## Class Diagram

```plantuml
@startuml
class User {
  +name: String
  +email: String
  +login(): Boolean
}
class Order {
  +id: int
  +total: Decimal
  +submit(): void
}
User "1" -- "*" Order : places
@enduml
```

## State Diagram

```plantuml
@startuml
[*] --> Idle
Idle --> Processing : start()
Processing --> Done : complete()
Processing --> Error : fail()
Error --> Idle : reset()
Done --> [*]

state Processing {
  [*] --> Validating
  Validating --> Executing
  Executing --> [*]
}
@enduml
```

## Gantt Chart

```plantuml
@startgantt
Project starts 2026-04-17
[Design] lasts 5 days
[Implementation] lasts 10 days
[Implementation] starts after [Design]'s end
[Testing] lasts 5 days
[Testing] starts after [Implementation]'s end
@endgantt
```

## Legend Support

**Native.** PlantUML supports inline legends:

```plantuml
legend right
  |= Color |= Meaning |
  |<#0072B2> | Core subsystem |
  |<#56B4E9> | External system |
  |<#D55E00> | Error path |
endlegend
```

## Common Pitfalls

- Missing `@startuml` / `@enduml` wrappers causes silent failure
- C4 macros (`!include <C4/C4_Context>`) require the C4-PlantUML library bundled in Kroki — use `c4plantuml` type instead of `plantuml` for C4 diagrams
- Gantt `lasts N days` must use integer — no fractional days
- `skinparam` must come before any diagram elements

## Upstream Docs

- https://plantuml.com/
- https://plantuml.com/sequence-diagram (sequence)
- https://plantuml.com/class-diagram (class)
- https://plantuml.com/state-diagram (state)
- https://plantuml.com/gantt-diagram (gantt)
