"""kroki_util — SVG composition, dark remap, CSS-var flatten, atomic write.

Pure Python (stdlib only). All functions are side-effect free except
atomic_write() and the __main__ CLI.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

# Light -> Dark hex remap (case-insensitive keys stored lowercase).
DARK_REMAP: dict[str, str] = {
    "#f7f7f7": "#2B2B2B",
    "#1f1f1f": "#E6E6E6",
    "#cccccc": "#444444",
    "#808080": "#A0A0A0",
}

# Kroki's SVG output commonly starts with `<?xml ...?>` and `<!DOCTYPE svg ...>`.
# xml.etree chokes on the external-DTD DOCTYPE, so we strip both before parsing.
# Substitution-only helpers (dark_remap, flatten_css_vars) don't need this.
_PREAMBLE_RE = re.compile(
    r"<\?xml[^>]*\?>\s*|<!DOCTYPE[^>\[]*(?:\[[^\]]*\])?[^>]*>\s*",
    re.IGNORECASE,
)


def _strip_preamble(svg: str) -> str:
    """Remove `<?xml ...?>` and `<!DOCTYPE ...>` so ElementTree can parse."""
    return _PREAMBLE_RE.sub("", svg, count=2).lstrip()


def atomic_write(path: Path, content: str | bytes, *, encoding: str = "utf-8") -> None:
    """Write content to path via temp file + atomic rename. Cleans up on error."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as fh:
        temp = Path(fh.name)
        data = content.encode(encoding) if isinstance(content, str) else content
        fh.write(data)
    try:
        temp.replace(path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def bounding_box(svg: str) -> tuple[float, float]:
    """Return (width, height) in user units. Prefers viewBox, falls back to width/height.

    Strips unit suffixes (pt, px, mm) from width/height attributes. Raises ValueError
    if neither viewBox nor width+height is present. Tolerates `<?xml?>` and
    `<!DOCTYPE>` preambles emitted by Kroki.
    """
    root = ET.fromstring(_strip_preamble(svg))
    viewbox = root.get("viewBox")
    if viewbox:
        parts = viewbox.replace(",", " ").split()
        if len(parts) == 4:
            return float(parts[2]), float(parts[3])

    def _strip(v: str | None) -> float | None:
        if v is None:
            return None
        m = re.match(r"^\s*([\d.]+)", v)
        return float(m.group(1)) if m else None

    w = _strip(root.get("width"))
    h = _strip(root.get("height"))
    if w is None or h is None:
        raise ValueError("SVG has no viewBox and no width/height")
    return w, h


_CSS_VAR_RE = re.compile(
    r"var\(\s*--[\w-]+\s*,\s*(#[0-9A-Fa-f]{3,8}|[\w-]+)\s*\)"
)


def flatten_css_vars(svg: str) -> str:
    """Replace every `var(--name, fallback)` with its fallback literal.

    Operates on the raw SVG string (covers <style> bodies, inline `style=`,
    and attribute values uniformly). `var(--name)` without a fallback is
    left unchanged in v1 — a higher-level caller (Plan 6 a11y-check) warns.
    """
    return _CSS_VAR_RE.sub(lambda m: m.group(1), svg)


_HEX6_RE = re.compile(r"#([0-9A-Fa-f]{6})(?![0-9A-Fa-f])")


def dark_remap(svg: str) -> str:
    """Swap light-palette hex codes for dark-palette hex codes.

    Operates on the raw SVG string — catches fill/stroke attributes,
    inline `style=`, and CSS rule bodies uniformly. Case-insensitive match
    against DARK_REMAP keys. Hex codes not in the table (including
    Okabe-Ito accents) are left untouched.
    """

    def _sub(match: re.Match[str]) -> str:
        key = ("#" + match.group(1)).lower()
        return DARK_REMAP.get(key, match.group(0))

    return _HEX6_RE.sub(_sub, svg)


def stitch_svgs_vertical(svgs: Sequence[str]) -> str:
    raise NotImplementedError


def build_legend_svg(diagram_svg: str, palette: dict[str, str]) -> str:
    raise NotImplementedError


def inject_caption(svg: str, caption: str) -> str:
    raise NotImplementedError


def _cli(argv: list[str] | None = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
