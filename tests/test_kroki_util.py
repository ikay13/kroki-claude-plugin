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
