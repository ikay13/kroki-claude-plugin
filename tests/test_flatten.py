"""Subprocess tests for scripts/flatten.sh."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "flatten.sh"


def run(*args):
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True)


def test_replaces_css_var_with_fallback(tmp_path):
    src = tmp_path / "in.svg"
    out = tmp_path / "out.svg"
    src.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect fill="var(--kroki-bg, #F7F7F7)"/>'
        '</svg>'
    )
    r = run(str(src), str(out))
    assert r.returncode == 0, r.stderr
    body = out.read_text()
    assert "var(" not in body
    assert "#F7F7F7" in body


def test_leaves_non_var_svg_unchanged(tmp_path):
    src = tmp_path / "in.svg"
    out = tmp_path / "out.svg"
    src.write_text('<svg><rect fill="#E69F00"/></svg>')
    r = run(str(src), str(out))
    assert r.returncode == 0
    assert out.read_text() == '<svg><rect fill="#E69F00"/></svg>'


def test_missing_input_exits_nonzero(tmp_path):
    r = run(str(tmp_path / "nope.svg"), str(tmp_path / "out.svg"))
    assert r.returncode != 0


def test_usage_no_args():
    r = run()
    assert r.returncode != 0
