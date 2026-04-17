"""Unit tests for kroki_util. Run: python3 -m pytest tests/test_kroki_util.py"""
from pathlib import Path

import pytest

from lib.kroki_util import (
    DARK_REMAP,
    atomic_write,
    bounding_box,
    build_legend_svg,
    dark_remap,
    flatten_css_vars,
    inject_caption,
    stitch_svgs_vertical,
)


def test_atomic_write_writes_content(tmp_path: Path) -> None:
    target = tmp_path / "out.svg"
    atomic_write(target, "<svg/>")
    assert target.read_text() == "<svg/>"
    # temp file must not linger
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_cleans_tempfile_on_error(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "out.svg"

    def boom(self, *a, **kw):
        raise OSError("disk full")

    # Force Path.replace to fail AFTER temp file is written.
    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(OSError):
        atomic_write(target, "<svg/>")
    assert not target.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_bounding_box_from_viewbox_with_kroki_preamble() -> None:
    # Real-world Kroki/PlantUML output shape: XML decl + external-DTD DOCTYPE.
    svg = (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"/>'
    )
    assert bounding_box(svg) == (400.0, 300.0)


def test_bounding_box_from_width_height() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="200pt" height="150pt"/>'
    assert bounding_box(svg) == (200.0, 150.0)


def test_flatten_css_vars_replaces_with_hex_fallback() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<style>.bg { fill: var(--kroki-bg, #F7F7F7); } '
        '.accent { stroke: var(--kroki-accent, #0072B2); }</style>'
        '<rect fill="var(--kroki-muted, #808080)"/></svg>'
    )
    out = flatten_css_vars(svg)
    assert "var(--kroki-bg" not in out
    assert "var(--kroki-accent" not in out
    assert "var(--kroki-muted" not in out
    assert "#F7F7F7" in out
    assert "#0072B2" in out
    assert "#808080" in out
