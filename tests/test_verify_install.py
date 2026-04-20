"""Subprocess tests for tests/verify-install.sh."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tests" / "verify-install.sh"


def run(*args):
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True)


def prepare(tmp_path: Path) -> dict:
    vault = tmp_path / "vault"
    (vault / ".obsidian" / "snippets").mkdir(parents=True)
    (vault / ".obsidian" / "snippets" / "kroki-theme.css").write_text("body{}")
    rules = tmp_path / "rules.md"
    rules.write_text(
        "4. Write a handoff document\n\n"
        "## Extension point: installer-appended instructions\n\n"
        "<!-- INSTALLER: kroki -->\n"
        "If the project has a `diagrams/` directory, invoke `kroki-session(mode=end, project=<project>)` to snapshot diagram changes.\n"
        "<!-- /INSTALLER: kroki -->\n"
    )
    state = tmp_path / "state"
    state.mkdir()
    return {"vault": vault, "rules": rules, "state": state}


def test_all_checks_pass(tmp_path):
    env = prepare(tmp_path)
    r = run(
        "--vault-root", str(env["vault"]),
        "--rules-file", str(env["rules"]),
        "--state-dir", str(env["state"]),
        "--skip-systemd", "--skip-pod", "--skip-smoke",
    )
    assert r.returncode == 0, r.stderr
    assert "CSS snippet" in r.stdout
    assert "session-continuity" in r.stdout
    assert "state dir" in r.stdout


def test_missing_css_snippet_fails(tmp_path):
    env = prepare(tmp_path)
    (env["vault"] / ".obsidian" / "snippets" / "kroki-theme.css").unlink()
    r = run(
        "--vault-root", str(env["vault"]),
        "--rules-file", str(env["rules"]),
        "--state-dir", str(env["state"]),
        "--skip-systemd", "--skip-pod", "--skip-smoke",
    )
    assert r.returncode != 0


def test_missing_step_5_fails(tmp_path):
    env = prepare(tmp_path)
    env["rules"].write_text("4. Handoff\n")
    r = run(
        "--vault-root", str(env["vault"]),
        "--rules-file", str(env["rules"]),
        "--state-dir", str(env["state"]),
        "--skip-systemd", "--skip-pod", "--skip-smoke",
    )
    assert r.returncode != 0
