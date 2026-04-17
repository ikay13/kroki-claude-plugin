# Svgbob Reference

Svgbob converts ASCII art to clean SVG. Like ditaa but with a different aesthetic — straighter lines, more "circuit-board" feel.

**Engine:** Companion container (`kroki-svgbob`)
**File extensions:** `.sbob`
**Kroki type string:** `svgbob`

## Basic boxes

```svgbob
   .---.                      .-------.
  /-o-/--                      \       \
.-/ / /->                   .----'       \
( *  \/                       \            '---'
 '-.  \                        \
    \ /                         \
     '                           V
.---------.                          .------------.
|  Hello  | *----> |-----> #------>  |  World     |
'---------'                          '------------'
```

## Circuit-style

```svgbob
   o----[A]----o----[R1]----o
                |
                |
              [LED]
                |
                v
   o----[B]----o
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Corners use `.` (top-left/top-right) and `'` (bottom-left/bottom-right) — `+` does NOT make a corner.
- Arrows: `-->` (right), `<--` (left), `^` and `v` (up/down).
- Diagonal lines via `/` and `\`.
- Whitespace matters — use spaces, never tabs.
- Long labels overflow the box visually but render correctly.

## Upstream Docs

- https://ivanceras.github.io/svgbob/
- https://github.com/ivanceras/svgbob
