# WireViz Reference

WireViz is a YAML-based DSL for documenting wire harnesses, cable assemblies, and electrical interconnects. Output shows connectors, conductors, and connections graphically.

**Engine:** Companion container (`kroki-wireviz`)
**File extensions:** `.wireviz`, `.yml` (YAML)
**Kroki type string:** `wireviz`

## Two-connector cable

```yaml
connectors:
  X1:
    type: D-Sub
    subtype: female
    pinlabels: [DCD, RX, TX, DTR, GND, DSR, RTS, CTS, RI]
  X2:
    type: D-Sub
    subtype: male
    pinlabels: [DCD, RX, TX, DTR, GND, DSR, RTS, CTS, RI]

cables:
  W1:
    gauge: 0.25 mm2
    length: 0.2
    color_code: DIN
    wirecount: 9
    shield: true

connections:
  -
    - X1: [1-9]
    - W1: [1-9]
    - X2: [1-9]
  -
    - X1: s
    - W1: s
```

## Three-connector harness

```yaml
connectors:
  PSU:
    type: Power Supply
    pinlabels: [+12V, GND]
  MB:
    type: Motherboard
    pinlabels: [+12V, GND]
  FAN:
    type: Fan
    pinlabels: [+12V, GND]

cables:
  C1:
    wirecount: 2
    colors: [RD, BK]
    length: 0.3
  C2:
    wirecount: 2
    colors: [RD, BK]
    length: 0.5

connections:
  -
    - PSU: [1, 2]
    - C1: [1, 2]
    - MB: [1, 2]
  -
    - MB: [1, 2]
    - C2: [1, 2]
    - FAN: [1, 2]
```

## Legend Support

**Stitch required.** Wire colors and connector types form an implicit legend; for explicit color-meaning legend, render a separate small WireViz with one connector showing every color.

## Common Pitfalls

- YAML indent is significant — use 2 spaces consistently, never tabs.
- `pinlabels` length must equal pin count.
- Standard color codes: `RD` (red), `BK` (black), `WH` (white), `BU` (blue), `GN` (green), `YE` (yellow), `OG` (orange), `BR` (brown), `VT` (violet), `GY` (grey), `PK` (pink). The `color_code` directive picks a national standard for auto-coloring.
- Pin range syntax: `[1-9]` works inside connection lists, expanding to `[1,2,3,4,5,6,7,8,9]`.
- `s` denotes the cable's shield — only valid when `shield: true` is set on the cable.

## Upstream Docs

- https://github.com/wireviz/WireViz
- https://github.com/wireviz/WireViz/blob/master/docs/syntax.md
