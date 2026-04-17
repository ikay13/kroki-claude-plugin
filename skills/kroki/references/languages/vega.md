# Vega Reference

Vega is a full visualization grammar — declarative JSON for arbitrary data charts. Lower-level than Vega-Lite (more verbose, more control). Use for advanced or programmable visualizations.

**Engine:** Core gateway (Vega has built-in support — no companion needed)
**File extensions:** `.vega` (JSON)
**Kroki type string:** `vega`

## Bar chart

```json
{
  "$schema": "https://vega.github.io/schema/vega/v5.json",
  "width": 400,
  "height": 200,
  "padding": 5,
  "data": [{
    "name": "table",
    "values": [
      {"category": "A", "amount": 28},
      {"category": "B", "amount": 55},
      {"category": "C", "amount": 43},
      {"category": "D", "amount": 91}
    ]
  }],
  "scales": [
    {
      "name": "x", "type": "band", "domain": {"data": "table", "field": "category"},
      "range": "width", "padding": 0.05
    },
    {
      "name": "y", "type": "linear", "domain": {"data": "table", "field": "amount"},
      "range": "height", "nice": true, "zero": true
    }
  ],
  "axes": [
    {"orient": "bottom", "scale": "x"},
    {"orient": "left", "scale": "y"}
  ],
  "marks": [{
    "type": "rect",
    "from": {"data": "table"},
    "encode": {
      "enter": {
        "x": {"scale": "x", "field": "category"},
        "width": {"scale": "x", "band": 1},
        "y": {"scale": "y", "field": "amount"},
        "y2": {"scale": "y", "value": 0}
      },
      "update": {"fill": {"value": "#0072B2"}}
    }
  }]
}
```

## Legend Support

**Native.** Vega's grammar treats legends as first-class — add a `legends` array to the spec.

```json
"legends": [{"fill": "color", "title": "Category"}]
```

## Common Pitfalls

- Always include `"$schema": "https://vega.github.io/schema/vega/v5.json"` so Kroki picks the right engine version.
- Data values are inline (`"values": [...]`) or by reference (`"url": "..."` — but the URL must be reachable from the Kroki container, which usually it is not — prefer inline).
- `marks` is the heart of the spec — every visible element needs a mark with explicit encoding.
- For most use cases, Vega-Lite is dramatically more concise — only drop down to Vega when you need a feature Vega-Lite cannot express.

## Upstream Docs

- https://vega.github.io/vega/
- https://vega.github.io/vega/examples/
