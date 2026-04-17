# Color Palette — Okabe-Ito

## Why Okabe-Ito?

Okabe & Ito (2008) derived 8 colors that remain distinguishable to all three
major types of color vision deficiency (deuteranopia, protanopia, tritanopia)
while printing acceptably in grayscale. It is the de-facto colorblind-safe
palette in scientific publishing.

## Semantic assignments

| Name | Hex | Role |
|------|-----|------|
| ink | #000000 | Text, default strokes |
| orange | #E69F00 | Warning, queue, async |
| sky | #56B4E9 | External system, API |
| green | #009E73 | Success, primary path |
| yellow | #F0E442 | Caution, optional |
| blue | #0072B2 | Core subsystem |
| vermilion | #D55E00 | Error, critical |
| pink | #CC79A7 | Test, auxiliary |

## Extended neutrals

| Light | Dark | Role |
|-------|------|------|
| #F7F7F7 | #2B2B2B | Background |
| #1F1F1F | #E6E6E6 | Text/stroke |
| #CCCCCC | #444444 | Subtle stroke |
| #808080 | #A0A0A0 | Muted text |

Only the neutrals remap in dark mode; Okabe-Ito accents stay identical.

## Layer gradient

For C4 / architectural layer tinting: L0 (outermost) through L4 (core),
Viridis-adjacent. Use sparingly — accent colors take priority when available.

## Machine-readable source

Canonical YAML: `styles/palette.yml`. Consumed by `a11y-check.sh`,
`render-with-legend.sh`, and `flatten.sh`.
