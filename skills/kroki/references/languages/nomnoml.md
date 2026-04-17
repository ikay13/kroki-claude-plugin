# nomnoml Reference

nomnoml is a concise UML-like text DSL with a hand-drawn-style render. Good for quick class/object sketches in design conversations.

**Engine:** Companion container (`kroki-nomnoml`)
**File extensions:** `.nml`
**Kroki type string:** `nomnoml`

## Basic class diagram

```nomnoml
[Pirate|- eyeCount: Int|o raid();o pillage()|
  [beard]--[parrot]
  [beard]-:>[foul mouth]
]
```

## Two classes with relationship

```nomnoml
[<frame>Decorator pattern|
  [<abstract>Component||+ operation()]
  [Client]--*[Component]
  [Decorator|- next: Component]
  [Decorator] +- next
  [Decorator]--:>[Component]
  [ConcreteComponent]--:>[Component]
  [ConcreteDecorator]--:>[Decorator]
]
```

## Style directives

```nomnoml
#stroke: #1F1F1F
#fill: #E8F4FD
#padding: 8

[A]->[B]->[C]
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Compartments inside a class are separated by `|`: `[Name|attr1: T;attr2: T|method1();method2()]`.
- Relationship syntax: `-->` (association), `--:>` (inheritance), `--*` (composition), `--o` (aggregation).
- Style directives (`#stroke`, `#fill`, `#padding`) must be at the top of the file before any class.
- Square brackets nest: `[Outer|[Inner1]; [Inner2]]`.

## Upstream Docs

- https://nomnoml.com/
- https://github.com/skanaar/nomnoml
