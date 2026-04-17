# ditaa Reference

ditaa (DIagrams Through Ascii Art) renders ASCII diagrams to SVG. The source IS visually meaningful — boxes, arrows, and lines drawn with text characters.

**Engine:** Companion container (`kroki-ditaa`)
**File extensions:** `.ditaa`
**Kroki type string:** `ditaa`

## Basic boxes and arrows

```ditaa
+--------+   +-------+    /-------\
| cEEF   | --+ ditaa +--> |       |
| Text   |   +-------+    |diagram|
|Document|   |!magic!|    |       |
|     {d}|   |  cGRE |    |   cPNK|
+---+----+   +-------+    \-------/
    :                         ^
    |       Lots of work      |
    \-------------------------/
```

## Color codes

Inside boxes, `cXXX` (3-char hex shorthand) sets a fill color:
- `cEEF` = light blue
- `cGRE` = green
- `cPNK` = pink
- `cRED` = red
- `cYEL` = yellow

## Shape modifiers

| Tag | Effect |
|-----|--------|
| `{d}` | Document shape |
| `{s}` | Storage shape |
| `{c}` | Cylinder (DB) |
| `{io}` | Input/output parallelogram |
| `{tr}` | Trapezoid |

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Lines must be drawn with `-`, `|`, `+` (corners) — `/` and `\` are rounded corners.
- Arrows: `-->` (right), `<--` (left), `^|v` for vertical.
- The diagram's bounding box is determined by the outermost `+` characters.
- Rendering is sensitive to whitespace — use spaces (NOT tabs) for alignment.
- Color codes go INSIDE the box on their own line.

## Upstream Docs

- http://ditaa.sourceforge.net/
