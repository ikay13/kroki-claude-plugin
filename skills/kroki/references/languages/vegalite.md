# Vega-Lite Reference

Vega-Lite is the high-level dialect of Vega — compact JSON for typical chart types. Faster to author than Vega for most cases.

**Engine:** Core gateway (Vega-Lite has built-in support — no companion needed)
**File extensions:** `.vegalite`, `.vl.json` (JSON)
**Kroki type string:** `vegalite`

## Bar chart (same data as Vega)

```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {
    "values": [
      {"category": "A", "amount": 28},
      {"category": "B", "amount": 55},
      {"category": "C", "amount": 43},
      {"category": "D", "amount": 91}
    ]
  },
  "mark": "bar",
  "encoding": {
    "x": {"field": "category", "type": "nominal"},
    "y": {"field": "amount", "type": "quantitative"}
  }
}
```

## Line chart with multiple series

```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {
    "values": [
      {"month": 1, "city": "NY", "temp": 32},
      {"month": 2, "city": "NY", "temp": 35},
      {"month": 3, "city": "NY", "temp": 45},
      {"month": 1, "city": "LA", "temp": 58},
      {"month": 2, "city": "LA", "temp": 60},
      {"month": 3, "city": "LA", "temp": 64}
    ]
  },
  "mark": "line",
  "encoding": {
    "x": {"field": "month", "type": "ordinal"},
    "y": {"field": "temp", "type": "quantitative"},
    "color": {"field": "city", "type": "nominal"}
  }
}
```

## Legend Support

**Native.** Vega-Lite generates legends automatically when you map a field to `color`, `shape`, or `size`. Customize with `"legend": {...}` inside the encoding.

## Common Pitfalls

- The `$schema` line is REQUIRED — without it Kroki may fall back to Vega and reject the spec.
- `"type"` in encoding must be one of: `quantitative`, `nominal`, `ordinal`, `temporal`. Wrong type silently produces a bad chart.
- `mark` is a string for simple cases (`"bar"`, `"line"`) or an object for parameters (`{"type": "bar", "color": "#0072B2"}`).
- Vega-Lite doesn't support all Vega features — for advanced needs (programmatic data transforms, custom scales) drop to Vega.

## Upstream Docs

- https://vega.github.io/vega-lite/
- https://vega.github.io/vega-lite/examples/
