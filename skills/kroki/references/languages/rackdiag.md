# rackdiag Reference

rackdiag is the BlockDiag-family server-rack DSL. It draws U-height racks with stacked equipment.

**Engine:** Companion container (`kroki-blockdiag`)
**File extensions:** `.rdia`
**Kroki type string:** `rackdiag`

## Single rack

```rackdiag
{
  16U;

  1: UPS [2U];
  3: DB Master [1U];
  4: DB Replica [1U];
  5: Web Server 1 [1U];
  6: Web Server 2 [1U];
  10: Switch (top-of-rack) [1U];
  16: KVM [1U];
}
```

## Two racks side by side

```rackdiag
{
  rack {
    8U;
    1: Switch [1U];
    2: App 1 [2U];
    4: App 2 [2U];
  }
  rack {
    8U;
    1: Switch [1U];
    2: DB [4U];
  }
}
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- The first line declares total rack height: `16U;` (note the `U` and semicolon).
- Slot positions count from the bottom (slot 1 = bottom).
- `[1U]` is the height of the equipment item — most rackmount gear is 1U or 2U.
- Slots cannot overlap; `1: Foo [2U]; 2: Bar [1U];` errors because Foo occupies slots 1-2.

## Upstream Docs

- http://blockdiag.com/en/nwdiag/rackdiag-examples.html
