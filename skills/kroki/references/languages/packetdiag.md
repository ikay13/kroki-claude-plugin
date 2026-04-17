# packetdiag Reference

packetdiag is the BlockDiag-family packet-structure DSL. It draws bit/byte fields with auto-layout, useful for protocol headers.

**Engine:** Companion container (`kroki-blockdiag`)
**File extensions:** `.pdia`
**Kroki type string:** `packetdiag`

## TCP header example

```packetdiag
{
  colwidth = 32
  node_height = 72

  0-15: Source Port
  16-31: Destination Port
  32-63: Sequence Number
  64-95: Acknowledgement Number
  96-99: Data Offset
  100-105: Reserved
  106: URG
  107: ACK
  108: PSH
  109: RST
  110: SYN
  111: FIN
  112-127: Window
  128-143: Checksum
  144-159: Urgent Pointer
}
```

## Generic header

```packetdiag
{
  colwidth = 16
  0-3: Version
  4-7: Header Length
  8-15: Type of Service
  16-31: Total Length
}
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Bit ranges use `start-end` (inclusive). Single bits use just the index.
- `colwidth` controls bits per row — typical values: `8`, `16`, `32`.
- Bits MUST be contiguous and in order — gaps cause render errors.
- Wider fields just span more columns; you don't say "byte 4-7", you say `32-63` for those four bytes.

## Upstream Docs

- http://blockdiag.com/en/nwdiag/packetdiag-examples.html
