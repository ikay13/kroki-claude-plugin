# WaveDrom Reference

WaveDrom is purpose-built for digital timing diagrams (clock signals, bus waveforms). Source is JSON5 with a domain-specific signal-pattern syntax.

**Engine:** Companion container (`kroki-wavedrom`)
**File extensions:** `.wavedrom` (JSON5)
**Kroki type string:** `wavedrom`

## Basic clock + data

```json
{ "signal": [
  { "name": "clk",  "wave": "p......" },
  { "name": "data", "wave": "x.345..", "data": ["A","B","C"] },
  { "name": "req",  "wave": "0.1..0." },
  { "name": "ack",  "wave": "0...1.0" }
]}
```

## Bus + control

```json
{ "signal": [
  { "name": "clk",     "wave": "p......." },
  { "name": "addr",    "wave": "x.34..5x", "data": ["0x10","0x14","0x18"] },
  { "name": "wdata",   "wave": "x.3..4.x", "data": ["DEADBEEF","CAFEBABE"] },
  { "name": "we",      "wave": "0.1..0.." },
  {},
  { "name": "rdata",   "wave": "x...3..x", "data": ["0xDEAD"] }
]}
```

## Wave pattern characters

| Char | Meaning |
|------|---------|
| `0` | Low |
| `1` | High |
| `p` / `P` | Positive-edge clock (regular / with arrows) |
| `n` / `N` | Negative-edge clock |
| `x` | Don't-care |
| `z` | High-impedance |
| `2`-`9` | Distinct data values (use color slot 2-9) |
| `.` | Hold previous state |
| `=` | Generic data |
| `\|` | Vertical separator |

## Legend Support

**Stitch required.** No native legend, but signal names ARE the legend.

## Common Pitfalls

- The `data` array fills in slots in the wave string in left-to-right order. Length must match the count of data slots (`3`-`9`, `=`).
- Empty objects `{}` insert a blank row separator.
- The whole spec must be valid JSON5 — JavaScript `//` comments are allowed but plain JSON parsers will reject them. Stick to JSON for safety.
- Time scale is uniform — one character = one cycle. Use `..` to hold for two cycles.

## Upstream Docs

- https://wavedrom.com/
- https://wavedrom.com/tutorial.html
