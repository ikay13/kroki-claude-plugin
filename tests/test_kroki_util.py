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


def test_dark_remap_swaps_palette() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect fill="#F7F7F7"/>'  # background -> dark bg
        '<text fill="#1F1F1F">hi</text>'  # emphasis text -> light text
        '<line stroke="#CCCCCC"/>'  # subtle stroke
        '<tspan fill="#808080"/></svg>'  # muted
    )
    out = dark_remap(svg)
    assert "#2B2B2B" in out
    assert "#E6E6E6" in out
    assert "#444444" in out
    assert "#A0A0A0" in out
    # Originals must be gone (case-insensitive check).
    low = out.lower()
    assert "#f7f7f7" not in low
    assert "#1f1f1f" not in low
    assert "#cccccc" not in low


def test_dark_remap_preserves_okabe_ito_accents() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect fill="#E69F00"/>'
        '<rect fill="#56B4E9"/>'
        '<rect fill="#009E73"/>'
        '<rect fill="#0072B2"/>'
        '<rect fill="#D55E00"/>'
        '<rect fill="#CC79A7"/></svg>'
    )
    out = dark_remap(svg)
    for accent in ("#E69F00", "#56B4E9", "#009E73", "#0072B2", "#D55E00", "#CC79A7"):
        assert accent in out


def test_stitch_svgs_vertical_combines_dimensions() -> None:
    a = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect/></svg>'
    b = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 30"><circle/></svg>'
    out = stitch_svgs_vertical([a, b])
    w, h = bounding_box(out)
    assert w == 100.0  # max of 100 and 80
    assert h == 80.0   # 50 + 30
    # Both child shapes must survive.
    assert "<rect" in out
    assert "<circle" in out


def test_build_legend_svg_auto_filters_used_colors() -> None:
    # Diagram uses only orange and sky; palette has four entries — legend
    # must contain only orange + sky labels, not green or vermilion.
    diagram = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50">'
        '<rect fill="#E69F00"/><circle stroke="#56B4E9"/></svg>'
    )
    palette = {
        "orange": "#E69F00",
        "sky": "#56B4E9",
        "green": "#009E73",
        "vermilion": "#D55E00",
    }
    legend = build_legend_svg(diagram, palette)
    assert "orange" in legend
    assert "sky" in legend
    assert "green" not in legend
    assert "vermilion" not in legend
    # Legend must be a valid SVG with a sensible bounding box.
    w, h = bounding_box(legend)
    assert w > 0 and h > 0


def test_inject_caption_adds_text_and_expands_viewbox() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"/>'
    out = inject_caption(svg, "Figure -- MSP Architecture")
    assert "Figure -- MSP Architecture" in out
    w, h = bounding_box(out)
    assert w == 100.0
    # Height grows by the caption strip (24px by convention).
    assert h > 50.0


from lib.kroki_util import (
    OKABE_ITO_PALETTE,
    contrast_ratio,
    wcag_aa_pass,
    extract_hex_colors,
    palette_violations,
    grayscale_collisions,
    colorblind_sim,
)


class TestContrastRatio:
    def test_black_on_white_is_21(self):
        assert abs(contrast_ratio("#000000", "#FFFFFF") - 21.0) < 0.01

    def test_white_on_white_is_1(self):
        assert abs(contrast_ratio("#FFFFFF", "#FFFFFF") - 1.0) < 0.01

    def test_symmetric(self):
        a = contrast_ratio("#1F1F1F", "#F7F7F7")
        b = contrast_ratio("#F7F7F7", "#1F1F1F")
        assert abs(a - b) < 0.01


class TestWcagAaPass:
    def test_normal_text_threshold_45(self):
        # contrast_ratio("#767676", "#FFFFFF") ~= 4.54 -> pass
        assert wcag_aa_pass("#767676", "#FFFFFF", large=False) is True
        assert wcag_aa_pass("#777777", "#FFFFFF", large=False) is False

    def test_large_text_threshold_30(self):
        assert wcag_aa_pass("#949494", "#FFFFFF", large=True) is True


class TestExtractHexColors:
    def test_finds_fill_and_stroke(self):
        svg = '<svg><rect fill="#FF0000" stroke="#00FF00"/></svg>'
        assert extract_hex_colors(svg) == {"#FF0000", "#00FF00"}

    def test_normalises_case(self):
        svg = '<svg><rect fill="#ff0000"/></svg>'
        assert "#FF0000" in extract_hex_colors(svg)

    def test_finds_in_style_attribute(self):
        svg = '<svg><rect style="fill:#123456;stroke:#abcdef"/></svg>'
        assert extract_hex_colors(svg) == {"#123456", "#ABCDEF"}

    def test_three_digit_hex_expanded(self):
        svg = '<svg><rect fill="#f0f"/></svg>'
        assert "#FF00FF" in extract_hex_colors(svg)


class TestPaletteViolations:
    def test_returns_non_palette_colors(self):
        svg = '<svg><rect fill="#E69F00"/><rect fill="#123456"/></svg>'
        assert palette_violations(svg, OKABE_ITO_PALETTE) == ["#123456"]

    def test_empty_when_all_in_palette(self):
        svg = '<svg><rect fill="#E69F00"/></svg>'
        assert palette_violations(svg, OKABE_ITO_PALETTE) == []


class TestGrayscaleCollisions:
    def test_detects_colors_with_similar_luminance(self):
        pairs = grayscale_collisions(["#777777", "#808080"], threshold=0.05)
        assert ("#777777", "#808080") in pairs or ("#808080", "#777777") in pairs

    def test_no_collision_for_black_and_white(self):
        assert grayscale_collisions(["#000000", "#FFFFFF"], threshold=0.05) == []


class TestColorblindSim:
    def test_deuteranopia_transforms_red(self):
        assert colorblind_sim("#FF0000", "deuteranopia") != "#FF0000"

    def test_protanopia_transforms_green(self):
        assert colorblind_sim("#00FF00", "protanopia") != "#00FF00"

    def test_returns_hex_format(self):
        result = colorblind_sim("#E69F00", "deuteranopia")
        assert result.startswith("#") and len(result) == 7

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError):
            colorblind_sim("#FF0000", "unknown-mode")
