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
