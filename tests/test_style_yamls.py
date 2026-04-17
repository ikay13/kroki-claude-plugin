"""Structural validation for styles/*.yml — no behavioral assertions."""
from pathlib import Path

import pytest
import yaml

STYLES = Path(__file__).resolve().parent.parent / "styles"


def load(name: str) -> dict:
    return yaml.safe_load((STYLES / name).read_text())


def test_palette_yaml_loads_and_has_expected_keys():
    data = load("palette.yml")
    assert "okabe_ito" in data
    assert "extended" in data
    assert "layer_gradient" in data
    assert set(data["okabe_ito"].keys()) >= {
        "ink", "orange", "sky", "green", "yellow", "blue", "vermilion", "pink",
    }
    for hex_ in data["okabe_ito"].values():
        assert hex_.startswith("#") and len(hex_) == 7


def test_symbols_yaml_loads_and_has_glyph_and_meaning():
    data = load("symbols.yml")
    assert "symbols" in data
    assert isinstance(data["symbols"], list)
    for entry in data["symbols"]:
        assert "glyph" in entry
        assert "meaning" in entry


def test_abbreviations_yaml_loads_and_has_entries():
    data = load("abbreviations.yml")
    assert "abbreviations" in data
    assert isinstance(data["abbreviations"], dict)
    # At least a few well-known abbreviations expected
    assert "API" in data["abbreviations"]
    for exp in data["abbreviations"].values():
        assert isinstance(exp, str) and len(exp) > 0


def test_legend_template_yaml_loads_with_placements_and_sections():
    data = load("legend-template.yml")
    assert "placements" in data
    assert "sections" in data
    assert "top-right" in data["placements"]
    assert {"color_key", "symbol_key", "abbreviations", "footer"} <= set(
        data["sections"].keys()
    )


def test_named_palettes_load_and_have_overrides():
    for name in ("nature", "ieee"):
        data = yaml.safe_load((STYLES / "palettes" / f"{name}.yml").read_text())
        assert "name" in data
        assert "base" in data
        assert data["base"] == "okabe_ito"
        assert "overrides" in data
        for hex_ in data["overrides"].values():
            assert hex_.startswith("#") and len(hex_) == 7
