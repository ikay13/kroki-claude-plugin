# actdiag Reference

actdiag is part of the BlockDiag family — a lane-aware activity-diagram DSL. Each activity sits in a `lane` (swimlane); arrows connect activities across lanes.

**Engine:** Companion container (`kroki-blockdiag`)
**File extensions:** `.adia`
**Kroki type string:** `actdiag`

## Activity diagram with lanes

```actdiag
{
  A -> B -> C -> D;

  lane user {
    label = "User"
    A; C;
  }
  lane system {
    label = "System"
    B; D;
  }
}
```

## Branching

```actdiag
{
  A -> B -> C;
  A -> D -> C;
  lane left  { A; B; }
  lane right { D; }
  lane out   { C; }
}
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Outer braces are mandatory (the entire diagram is a block).
- Activity nodes are declared by appearing in any arrow chain — no separate node block needed.
- Lane labels go inside the `lane` block as `label = "..."`.
- Same node can only appear in one lane — splitting an activity requires renaming.

## Upstream Docs

- http://blockdiag.com/en/actdiag/
