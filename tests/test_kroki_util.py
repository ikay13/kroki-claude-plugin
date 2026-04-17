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
