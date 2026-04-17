# Symbolator Reference

Symbolator generates entity-symbol diagrams from VHDL source. The Kroki gateway needs the patched image (`~/kroki/Dockerfile.kroki-patched`) to run symbolator correctly.

**Engine:** Companion container (`kroki-symbolator` — patched build)
**File extensions:** `.vhdl`, `.vhd`
**Kroki type string:** `symbolator`

## Minimal entity

```vhdl
library ieee;
use ieee.std_logic_1164.all;

entity counter is
  generic (
    WIDTH : positive := 8
  );
  port (
    clk    : in  std_logic;
    rst_n  : in  std_logic;
    enable : in  std_logic;
    count  : out std_logic_vector(WIDTH-1 downto 0);
    overflow : out std_logic
  );
end entity counter;

architecture rtl of counter is
begin
  -- Architecture body required for valid VHDL
  -- but not used for symbol diagram
end architecture rtl;
```

## Multi-entity file

```vhdl
library ieee;
use ieee.std_logic_1164.all;

entity adder is
  port (
    a, b : in  std_logic_vector(7 downto 0);
    sum  : out std_logic_vector(8 downto 0)
  );
end entity adder;

entity multiplier is
  port (
    a, b   : in  std_logic_vector(7 downto 0);
    product : out std_logic_vector(15 downto 0)
  );
end entity multiplier;
```

Symbolator renders both entities — typically one is shown by default; specify which via Kroki options if needed.

## Legend Support

**Stitch required.** No native legend; the symbol IS the legend.

## Status on this host (2026-04-17)

**KNOWN-BROKEN.** The running kroki gateway is the unpatched `yuzutech/kroki` image (per `~/kroki/docker-compose.yml`). Symbolator returns an empty SVG (HTTP 200 with 0-byte body) for every request. The patched gateway build prepared at `~/kroki/Dockerfile.kroki-patched` was never wired into the running pod. Until the compose file points at the patched image, **all symbolator renders will silently fail.** Fix is deferred to Plan 6 (Polish & Install), which owns infra remediation.

## Common Pitfalls

- VHDL syntax must parse — symbolator runs a real VHDL frontend. Architecture body can be empty but must exist.
- The patched gateway image is required — vanilla `yuzutech/kroki` symbolator is broken (see "Status on this host" above). Verify which image is running with: `podman ps --filter pod=kroki --format '{{.Image}}'`.
- Generic and port names render exactly as written — no automatic case normalization.
- Library imports (`library ieee;`, `use ieee.std_logic_1164.all;`) are required even though only the symbol is rendered.

## Upstream Docs

- https://kevinpt.github.io/symbolator/
- https://github.com/kevinpt/symbolator
- Kroki patch source: `~/kroki/Dockerfile.kroki-patched`
