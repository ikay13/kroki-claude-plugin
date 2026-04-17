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
    raise NotImplementedError


def bounding_box(svg: str) -> tuple[float, float]:
    raise NotImplementedError


def flatten_css_vars(svg: str) -> str:
    raise NotImplementedError


def dark_remap(svg: str) -> str:
    raise NotImplementedError


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
