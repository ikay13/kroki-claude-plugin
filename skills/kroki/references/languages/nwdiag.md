# nwdiag Reference

nwdiag is the BlockDiag-family network-topology DSL. It draws hosts on subnets ("networks") with addresses.

**Engine:** Companion container (`kroki-blockdiag`)
**File extensions:** `.ndia`
**Kroki type string:** `nwdiag`

## Two-network example

```nwdiag
nwdiag {
  network dmz {
    address = "210.x.x.x/24"

    web01 [address = "210.x.x.1"];
    web02 [address = "210.x.x.2"];
  }
  network internal {
    address = "172.x.x.x/24";

    web01 [address = "172.x.x.1"];
    web02 [address = "172.x.x.2"];
    db01;
    db02;
  }
}
```

## Single network with router

```nwdiag
nwdiag {
  internet [shape = cloud];
  internet -- router;

  network office {
    address = "10.0.0.0/24"
    router  [address = "10.0.0.1"]
    laptop  [address = "10.0.0.10"];
    printer [address = "10.0.0.20"];
  }
}
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- The wrapper keyword is `nwdiag` (not bare braces — different from blockdiag).
- A host on multiple networks must be repeated in each `network` block; nwdiag draws it once and connects automatically.
- `address = "..."` on a host is a label, not a validated IP — type whatever you want there.
- Shapes: `cloud`, `internet`, `database`, `cisco-*` (a few Cisco icon names supported).

## Upstream Docs

- http://blockdiag.com/en/nwdiag/
