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
        "\n"
        "## Extension point: installer-appended instructions\n"
        "\n"
        "Plugins and installers extend session-continuity behavior by appending\n"
        "HTML-comment-bracketed blocks below this paragraph.\n"
    )
    return f


def fake_rules_without_extension_section(tmp: Path) -> Path:
    """Fixture for preflight-failure test — has no Extension-point section."""
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


def test_install_appends_kroki_extension_block_idempotently(tmp_path):
    """Install appends the kroki marker block; second run is idempotent (no duplicate)."""
    rules = fake_rules(tmp_path)
    args = [
        "--vault-root", str(fake_vault(tmp_path)),
        "--rules-file", str(rules),
        "--state-dir", str(tmp_path / "state"),
        "--skip-systemd",
        "--skip-smoke",
    ]
    # First run — fresh append
    r1 = run(*args)
    assert r1.returncode == 0, r1.stderr
    body = rules.read_text()
    assert "<!-- INSTALLER: kroki -->" in body
    assert "<!-- /INSTALLER: kroki -->" in body
    assert "kroki-session" in body  # instruction content still present

    # Second run — idempotent
    r2 = run(*args)
    assert r2.returncode == 0, r2.stderr
    body_after = rules.read_text()
    assert body_after.count("<!-- INSTALLER: kroki -->") == 1, \
        "Second install run must not duplicate the marker block"


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


def test_install_fails_if_rules_file_lacks_extension_section(tmp_path):
    """install.sh preflight must fail non-zero with a concrete error when the rules file
    lacks the '## Extension point: installer-appended instructions' section."""
    rules = fake_rules_without_extension_section(tmp_path)
    r = run(
        "--vault-root", str(fake_vault(tmp_path)),
        "--rules-file", str(rules),
        "--state-dir", str(tmp_path / "state"),
        "--skip-systemd",
        "--skip-smoke",
    )
    assert r.returncode != 0, "install.sh must fail when Extension-point section missing"
    assert "Extension point" in r.stderr, \
        f"stderr should mention Extension point; got: {r.stderr}"
    # Rules file must not have been mutated
    body = rules.read_text()
    assert "<!-- INSTALLER: kroki -->" not in body, \
        "Rules file must not be mutated when preflight fails"


def test_install_appends_kroki_block_between_markers(tmp_path):
    """The appended block has both open and close markers, with the kroki-session
    instruction line between them (contract shape, not just content)."""
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

    open_idx = body.find("<!-- INSTALLER: kroki -->")
    close_idx = body.find("<!-- /INSTALLER: kroki -->")
    assert open_idx != -1, "open marker missing"
    assert close_idx != -1, "close marker missing"
    assert open_idx < close_idx, "open marker must precede close marker"

    between = body[open_idx:close_idx]
    assert "kroki-session(mode=end, project=<project>)" in between, \
        "kroki-session instruction must appear between markers"
