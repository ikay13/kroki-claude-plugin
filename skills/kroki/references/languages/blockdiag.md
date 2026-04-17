# blockdiag Reference

blockdiag is the root of the BlockDiag family — a generic block-and-arrow DSL with automatic layout. Use for high-level flows where you don't need swimlanes or topology.

**Engine:** Companion container (`kroki-blockdiag`)
**File extensions:** `.bdia`
**Kroki type string:** `blockdiag`

## Basic flow

```blockdiag
{
  start -> auth -> handler -> done;
  start [color = "#56B4E9"];
  done  [color = "#009E73"];
}
```

## Grouping

```blockdiag
{
  user -> web -> api -> db;
  group {
    label = "Backend"
    color = "#E8F4FD"
    api; db;
  }
}
```

## Branching with shapes

```blockdiag
{
  start -> decide;
  decide [shape = diamond, label = "OK?"];
  decide -> success;
  decide -> failure;
}
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Outer braces are mandatory.
- Default node shape is `box`; use `shape = diamond | ellipse | minidiamond | beginpoint | endpoint` for variety.
- Edge labels use `[label = "..."]` on the edge: `A -> B [label = "yes"]`.
- Group blocks must contain at least one node.

## Upstream Docs

- http://blockdiag.com/en/blockdiag/
