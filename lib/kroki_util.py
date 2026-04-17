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


def _fmt_dim(v: float) -> str:
    """Format a dimension as int when whole, else as float."""
    return str(int(v)) if v == int(v) else str(v)


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
    """Compose input SVGs vertically into a single SVG.

    New viewBox is (0, 0, max_width, sum_height). Each input is nested as a
    child <svg> element with y offset equal to the accumulated height. The
    namespace declaration is emitted once on the outer <svg>.
    """
    if not svgs:
        raise ValueError("stitch_svgs_vertical requires at least one SVG")
    dims = [bounding_box(s) for s in svgs]
    total_w = max(w for w, _ in dims)
    total_h = sum(h for _, h in dims)

    children: list[str] = []
    y = 0.0
    for svg, (w, h) in zip(svgs, dims):
        inner = ET.fromstring(_strip_preamble(svg))
        inner.set("x", "0")
        inner.set("y", _fmt_dim(y))
        inner.set("width", _fmt_dim(w))
        inner.set("height", _fmt_dim(h))
        # Force viewBox so nested coordinate system matches input.
        if inner.get("viewBox") is None:
            inner.set("viewBox", f"0 0 {_fmt_dim(w)} {_fmt_dim(h)}")
        children.append(ET.tostring(inner, encoding="unicode"))
        y += h

    body = "".join(children)
    return (
        f'<svg xmlns="{SVG_NS}" '
        f'viewBox="0 0 {_fmt_dim(total_w)} {_fmt_dim(total_h)}" '
        f'width="{_fmt_dim(total_w)}" height="{_fmt_dim(total_h)}">{body}</svg>'
    )


def build_legend_svg(diagram_svg: str, palette: dict[str, str]) -> str:
    """Generate a legend SVG showing only palette entries used in the diagram.

    Scans diagram_svg for each hex in `palette` (case-insensitive, with a
    trailing word boundary so `#000` doesn't spuriously match inside
    `#0000FF`). Produces a one-column stitch of swatches + labels. Each row
    is 24px tall; swatch is 16x16, label starts at x=24.
    """

    def _present(hex_: str) -> bool:
        pattern = re.compile(re.escape(hex_) + r"(?![0-9A-Fa-f])", re.IGNORECASE)
        return pattern.search(diagram_svg) is not None

    used = [(name, hex_) for name, hex_ in palette.items() if _present(hex_)]
    if not used:
        return (
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 1 1" width="1" height="1"/>'
        )

    row_h = 24
    label_x = 24
    swatch = 16
    width = 200
    height = row_h * len(used)

    rows: list[str] = []
    for i, (name, hex_) in enumerate(used):
        y = i * row_h
        rows.append(
            f'<rect x="0" y="{y + (row_h - swatch) // 2}" '
            f'width="{swatch}" height="{swatch}" fill="{hex_}"/>'
            f'<text x="{label_x}" y="{y + row_h - 6}" '
            f'font-family="sans-serif" font-size="14">{name}</text>'
        )

    return (
        f'<svg xmlns="{SVG_NS}" '
        f'viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">{"".join(rows)}</svg>'
    )


def inject_caption(svg: str, caption: str) -> str:
    """Append a caption strip (24px tall) below the diagram.

    Produces a new outer <svg> that stacks the input diagram on top and a
    <text> element underneath. Implemented as a stitch with a generated
    caption-SVG so sizing is consistent with stitch_svgs_vertical().
    """
    w, _ = bounding_box(svg)
    caption_h = 24
    # Escape special chars so arbitrary text doesn't break XML.
    safe = (
        caption.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    caption_svg = (
        f'<svg xmlns="{SVG_NS}" '
        f'viewBox="0 0 {_fmt_dim(w)} {caption_h}" '
        f'width="{_fmt_dim(w)}" height="{caption_h}">'
        f'<text x="4" y="{caption_h - 8}" '
        f'font-family="sans-serif" font-size="12" font-style="italic">'
        f'{safe}</text></svg>'
    )
    return stitch_svgs_vertical([svg, caption_svg])


# ---------------------------------------------------------------------------
# Accessibility helpers (advisory — called by a11y-check.sh)
# ---------------------------------------------------------------------------

OKABE_ITO_PALETTE: dict[str, str] = {
    "ink": "#000000",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermilion": "#D55E00",
    "pink": "#CC79A7",
    "bg-light": "#F7F7F7",
    "bg-dark": "#2B2B2B",
    "muted": "#808080",
    "emphasis": "#1F1F1F",
    "subtle-stroke": "#CCCCCC",
    "white": "#FFFFFF",
}

_HEX_ANY_RE = re.compile(r"#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})(?![0-9A-Fa-f])")


def _hex_to_rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(hex_: str) -> float:
    """WCAG relative luminance (sRGB -> linear -> weighted sum)."""

    def chan(c: int) -> float:
        cs = c / 255.0
        return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4

    r, g, b = _hex_to_rgb(hex_)
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio: (L_lighter + 0.05) / (L_darker + 0.05). Range 1..21."""
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter, darker = (l1, l2) if l1 > l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def wcag_aa_pass(fg: str, bg: str, *, large: bool = False) -> bool:
    """WCAG AA pass: normal text >= 4.5:1; large text (18pt+ / 14pt+ bold) >= 3.0:1."""
    threshold = 3.0 if large else 4.5
    return contrast_ratio(fg, bg) >= threshold


def extract_hex_colors(svg: str) -> set[str]:
    """All hex colors in the SVG, normalised to uppercase 7-char (#RRGGBB)."""
    out: set[str] = set()
    for m in _HEX_ANY_RE.finditer(svg):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        out.add("#" + h.upper())
    return out


def palette_violations(svg: str, palette: dict[str, str]) -> list[str]:
    """Hex colors in the SVG that are not in the palette. Sorted for stable output."""
    allowed = {v.upper() for v in palette.values()}
    return sorted(c for c in extract_hex_colors(svg) if c not in allowed)


def grayscale_collisions(
    colors: list[str], *, threshold: float = 0.05
) -> list[tuple[str, str]]:
    """Pairs of colors whose relative luminance differs by less than `threshold`."""
    lums = [(c, _relative_luminance(c)) for c in colors]
    out: list[tuple[str, str]] = []
    for i in range(len(lums)):
        for j in range(i + 1, len(lums)):
            if abs(lums[i][1] - lums[j][1]) < threshold:
                out.append((lums[i][0], lums[j][0]))
    return out


# Brettel/Vienot colorblind simulation matrices (sRGB approximation).
_CB_MATRICES: dict[str, tuple[tuple[float, float, float], ...]] = {
    "deuteranopia": (
        (0.367, 0.861, -0.228),
        (0.280, 0.673, 0.047),
        (-0.012, 0.043, 0.969),
    ),
    "protanopia": (
        (0.152, 1.053, -0.205),
        (0.115, 0.786, 0.099),
        (-0.004, -0.048, 1.052),
    ),
    "tritanopia": (
        (1.256, -0.077, -0.179),
        (-0.078, 0.931, 0.148),
        (0.005, 0.691, 0.304),
    ),
}


def colorblind_sim(hex_: str, mode: str) -> str:
    """Approximate a colorblind person's perception of the given color.

    Modes: deuteranopia, protanopia, tritanopia. Returns uppercase `#RRGGBB`.
    """
    if mode not in _CB_MATRICES:
        raise ValueError(f"unknown colorblind mode: {mode}")
    m = _CB_MATRICES[mode]
    r, g, b = (c / 255.0 for c in _hex_to_rgb(hex_))
    rr = m[0][0] * r + m[0][1] * g + m[0][2] * b
    gg = m[1][0] * r + m[1][1] * g + m[1][2] * b
    bb = m[2][0] * r + m[2][1] * g + m[2][2] * b
    clamp = lambda v: max(0, min(255, int(round(v * 255))))
    return "#{:02X}{:02X}{:02X}".format(clamp(rr), clamp(gg), clamp(bb))


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kroki_util",
        description="SVG composition + remap + flatten helpers",
    )
    parser.add_argument(
        "--op",
        required=True,
        choices=["dark-remap", "flatten", "caption"],
        help="Operation to perform",
    )
    parser.add_argument("--in", dest="input", required=True, help="Input SVG path")
    parser.add_argument("--out", dest="output", required=True, help="Output SVG path")
    parser.add_argument("--caption", default="", help="Caption text (only for --op caption)")
    args = parser.parse_args(argv)

    src = Path(args.input).read_text(encoding="utf-8")
    if args.op == "dark-remap":
        result = dark_remap(src)
    elif args.op == "flatten":
        result = flatten_css_vars(src)
    elif args.op == "caption":
        result = inject_caption(src, args.caption)
    else:  # argparse guarantees unreachable
        return 2

    atomic_write(Path(args.output), result)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
