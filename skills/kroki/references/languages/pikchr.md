# Pikchr Reference

Pikchr is a modern descendant of the PIC language (originally from troff). Compact, declarative, with named directions and procedural flow.

**Engine:** Companion container (`kroki-pikchr`)
**File extensions:** `.pik`
**Kroki type string:** `pikchr`

## Basic boxes

```pikchr
box "Hello" fill skyblue
arrow
box "World" fill salmon
```

## Loop structure

```pikchr
right
B1: box "Start" fill lightgreen
arrow
B2: box "Process" fill lightyellow
arrow
B3: box "Decide" fill lightpink
arrow "yes" above
B4: box "Done"
arrow from B3.s down then left until even with B1.s then up to B1.s "no" below
```

## Connectors with labels

```pikchr
A: box "Auth Service"
move right 1
B: box "API Gateway"
move right 1
C: box "DB"

arrow from A.e to B.w "1: token"
arrow from B.e to C.w "2: query"
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Direction is set with bare keywords: `right`, `down`, `left`, `up`. Subsequent objects flow in that direction.
- Object types: `box`, `circle`, `ellipse`, `oval`, `cylinder`, `arrow`, `line`, `move`.
- Named objects: `B1: box "..."` — referenced later as `B1.n`, `B1.s`, `B1.e`, `B1.w` (compass cardinal points).
- Strings without quotes after the object are labels; with quotes are explicit text.
- Arrow paths can chain: `from A.e to B.n then to C.s then ...`.

## Upstream Docs

- https://pikchr.org/
- https://pikchr.org/home/doc/trunk/doc/grammar.md
