"""Subprocess tests for scripts/install.sh (idempotent installer)."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "install.sh"


def run(*args, **kw):
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, **kw)


def fake_vault(tmp: Path) -> Path:
    v = tmp / "vault"
    (v / ".obsidian" / "snippets").mkdir(parents=True)
    return v


def fake_rules(tmp: Path) -> Path:
    f = tmp / "session-continuity.md"
    f.write_text(
        "# Rule: Session Continuity\n\n"
        "At the end of every session involving project work:\n"
        "1. Update `project_session_state.md`\n"
        "2. Update the Obsidian tracker\n"
        "3. Add a session log\n"
        "4. Write a handoff document\n"
    )
    return f


def test_installs_css_snippet(tmp_path):
    v = fake_vault(tmp_path)
    r = run(
        "--vault-root", str(v),
        "--rules-file", str(fake_rules(tmp_path)),
        "--state-dir", str(tmp_path / "state"),
        "--skip-systemd",
        "--skip-smoke",
    )
    assert r.returncode == 0, r.stderr
    assert (v / ".obsidian" / "snippets" / "kroki-theme.css").exists()


def test_appends_step_5_to_rules(tmp_path):
    rules = fake_rules(tmp_path)
    r = run(
        "--vault-root", str(fake_vault(tmp_path)),
        "--rules-file", str(rules),
        "--state-dir", str(tmp_path / "state"),
        "--skip-systemd",
        "--skip-smoke",
    )
    assert r.returncode == 0, r.stderr
    body = rules.read_text()
    assert "kroki-session" in body
    assert "5." in body


def test_idempotent_no_duplicate_step_5(tmp_path):
    rules = fake_rules(tmp_path)
    args = [
        "--vault-root", str(fake_vault(tmp_path)),
        "--rules-file", str(rules),
        "--state-dir", str(tmp_path / "state"),
        "--skip-systemd",
        "--skip-smoke",
    ]
    run(*args)
    run(*args)
    body = rules.read_text()
    assert body.count("kroki-session") == 1


def test_creates_state_dir(tmp_path):
    state = tmp_path / "state"
    r = run(
        "--vault-root", str(fake_vault(tmp_path)),
        "--rules-file", str(fake_rules(tmp_path)),
        "--state-dir", str(state),
        "--skip-systemd",
        "--skip-smoke",
    )
    assert r.returncode == 0, r.stderr
    assert state.is_dir()


def test_missing_vault_exits_nonzero(tmp_path):
    r = run(
        "--vault-root", str(tmp_path / "does-not-exist"),
        "--rules-file", str(fake_rules(tmp_path)),
        "--state-dir", str(tmp_path / "state"),
        "--skip-systemd",
        "--skip-smoke",
    )
    assert r.returncode != 0
