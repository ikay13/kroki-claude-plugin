# Legend Template

Machine-readable legend layout. Consumed by `render-with-legend.sh`.

## Sections

1. **Color key** — auto-filtered to palette entries used in the diagram.
2. **Symbol key** — auto-filtered to glyphs used.
3. **Abbreviations** — auto-filtered to acronyms in diagram text.
4. **Footer** (optional) — date + source commit hash.

## Placements

Ten options (`top-right` default, `top-left`, `bottom-left`, `bottom-right`,
`below`, `beside-right`, `beside-left`, `embedded`, `overlay`, `none`).
Anchor + offset controls where the legend attaches relative to the diagram
bounding box. `overlay` uses partial opacity for in-diagram placement.

## Sizing modes

`screen` (default, 14px font), `print` (10pt, thicker strokes),
`poster` (large format). Maps to language-specific directives where native
legends are used.

## Canonical YAML

`styles/legend-template.yml`
