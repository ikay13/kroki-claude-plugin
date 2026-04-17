"""Subprocess tests for scripts/a11y-check.sh."""
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
A11Y = REPO_ROOT / "scripts" / "a11y-check.sh"


def run(*args, **kw):
    return subprocess.run([str(A11Y), *args], capture_output=True, text=True, **kw)


def write_svg(path: Path, *fills: str) -> None:
    rects = "".join(f'<rect fill="{f}"/>' for f in fills)
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{rects}</svg>')


def test_exits_zero_on_clean_svg(tmp_path):
    svg = tmp_path / "clean.svg"
    write_svg(svg, "#E69F00", "#0072B2")
    r = run(str(svg))
    assert r.returncode == 0


def test_exits_zero_on_problematic_svg(tmp_path, monkeypatch):
    monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path / "state"))
    svg = tmp_path / "dirty.svg"
    write_svg(svg, "#123456")
    r = run(str(svg))
    assert r.returncode == 0
    assert "palette" in (r.stdout + r.stderr).lower()


def test_writes_report_file(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("KROKI_STATE_DIR", str(state))
    svg = tmp_path / "sample.svg"
    write_svg(svg, "#E69F00")
    run(str(svg))
    report = state / "a11y-reports" / "sample.log"
    assert report.exists()


def test_missing_file_exits_nonzero(tmp_path):
    r = run(str(tmp_path / "does-not-exist.svg"))
    assert r.returncode != 0


def test_usage_no_args():
    r = run()
    assert r.returncode != 0
    assert "usage" in (r.stdout + r.stderr).lower()
