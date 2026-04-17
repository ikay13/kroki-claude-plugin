"""Subprocess tests for scripts/render-with-legend.sh."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "render-with-legend.sh"
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def run(*args):
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True)


def test_produces_light_and_dark_with_legend(tmp_path):
    fixture = FIXTURES / "plantuml.fixture.txt"
    src = tmp_path / "arch-legend-test.puml"
    src.write_text(fixture.read_text())

    r = run(str(src), "--type", "plantuml", "--out", str(tmp_path))
    assert r.returncode == 0, r.stderr

    light = tmp_path / "arch-legend-test.light.svg"
    dark = tmp_path / "arch-legend-test.dark.svg"
    assert light.exists() and light.stat().st_size > 0
    assert dark.exists() and dark.stat().st_size > 0

    content = light.read_text()
    assert "<svg" in content


def test_usage_no_args():
    r = run()
    assert r.returncode != 0


def test_handles_render_failure(tmp_path):
    # plantuml is forgiving of many malformed inputs (@startuml\n@startuml\n
    # renders without error). Use XML-breaking syntax that forces a 400 from Kroki.
    bad = tmp_path / "bad.puml"
    bad.write_text("<invalid xml & broken plantuml>")
    r = run(str(bad), "--type", "plantuml", "--out", str(tmp_path))
    assert r.returncode != 0
