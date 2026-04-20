"""Subprocess tests for scripts/install.sh (idempotent installer)."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "install.sh"

OLD_MARKER_OPEN = "<!-- INSTALLER: kroki -->"
OLD_MARKER_CLOSE = "<!-- /INSTALLER: kroki -->"
NEW_MARKER_OPEN = "<!-- INSTALLER: kroki-session -->"
NEW_MARKER_CLOSE = "<!-- /INSTALLER: kroki-session -->"


def run(*args, **kw):
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, **kw)


def fake_vault(tmp: Path) -> Path:
    v = tmp / "vault"
    (v / ".obsidian" / "snippets").mkdir(parents=True)
    return v


def fake_rules(tmp: Path) -> Path:
    """Baseline rules file: Extension-point section present, no INSTALLER block yet."""
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


def fake_rules_with_old_marker(tmp: Path) -> Path:
    """Rules file that simulates a v0.9.0 install — has the old INSTALLER: kroki block."""
    f = tmp / "session-continuity-old.md"
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
        "\n"
        "<!-- INSTALLER: kroki -->\n"
        "If the project has a `diagrams/` directory, invoke "
        "`kroki-session(mode=end, project=<project>)` to snapshot diagram changes.\n"
        "<!-- /INSTALLER: kroki -->\n"
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


def _install_args(vault, rules, state):
    return [
        "--vault-root", str(vault),
        "--rules-file", str(rules),
        "--state-dir", str(state),
        "--skip-systemd",
        "--skip-smoke",
    ]


def test_installs_css_snippet(tmp_path):
    v = fake_vault(tmp_path)
    r = run(*_install_args(v, fake_rules(tmp_path), tmp_path / "state"))
    assert r.returncode == 0, r.stderr
    assert (v / ".obsidian" / "snippets" / "kroki-theme.css").exists()


# ---------------------------------------------------------------------------
# Step 2 — fresh install (no old marker, no new marker)
# ---------------------------------------------------------------------------

def test_fresh_install_appends_new_marker(tmp_path):
    """Fresh install (no prior marker): appends <!-- INSTALLER: kroki-session --> block."""
    rules = fake_rules(tmp_path)
    r = run(*_install_args(fake_vault(tmp_path), rules, tmp_path / "state"))
    assert r.returncode == 0, r.stderr
    body = rules.read_text()
    assert NEW_MARKER_OPEN in body, "new open marker must be appended"
    assert NEW_MARKER_CLOSE in body, "new close marker must be appended"
    assert OLD_MARKER_OPEN not in body, "old marker must NOT appear on fresh install"


def test_fresh_install_new_marker_idempotent(tmp_path):
    """Running install twice on a fresh file leaves exactly one kroki-session block."""
    rules = fake_rules(tmp_path)
    args = _install_args(fake_vault(tmp_path), rules, tmp_path / "state")
    r1 = run(*args)
    assert r1.returncode == 0, r1.stderr
    r2 = run(*args)
    assert r2.returncode == 0, r2.stderr
    body = rules.read_text()
    assert body.count(NEW_MARKER_OPEN) == 1, \
        "Second install run must not duplicate the kroki-session marker block"
    assert OLD_MARKER_OPEN not in body, "old marker must not appear after idempotent run"


# ---------------------------------------------------------------------------
# Step 2 — migration path (old v0.9.0 marker present)
# ---------------------------------------------------------------------------

def test_migration_removes_old_marker_appends_new(tmp_path):
    """install.sh migrates v0.9.0 INSTALLER: kroki block to INSTALLER: kroki-session."""
    rules = fake_rules_with_old_marker(tmp_path)
    r = run(*_install_args(fake_vault(tmp_path), rules, tmp_path / "state"))
    assert r.returncode == 0, r.stderr
    body = rules.read_text()
    # New marker must be present
    assert NEW_MARKER_OPEN in body, "new open marker must be present after migration"
    assert NEW_MARKER_CLOSE in body, "new close marker must be present after migration"
    # Old marker must be gone
    assert OLD_MARKER_OPEN not in body, "old open marker must be removed by migration"
    assert OLD_MARKER_CLOSE not in body, "old close marker must be removed by migration"


def test_migration_idempotent_second_run(tmp_path):
    """Running install.sh twice on a v0.9.0 file leaves exactly one new block."""
    rules = fake_rules_with_old_marker(tmp_path)
    args = _install_args(fake_vault(tmp_path), rules, tmp_path / "state")
    r1 = run(*args)
    assert r1.returncode == 0, r1.stderr
    r2 = run(*args)
    assert r2.returncode == 0, r2.stderr
    body = rules.read_text()
    assert body.count(NEW_MARKER_OPEN) == 1, \
        "Two installs on migrated file must leave exactly one kroki-session block"
    assert OLD_MARKER_OPEN not in body, "old marker must remain absent after second run"


# ---------------------------------------------------------------------------
# Step 2 — new marker shape (content contract)
# ---------------------------------------------------------------------------

def test_new_marker_block_shape(tmp_path):
    """Appended kroki-session block has open/close markers wrapping the instruction text."""
    rules = fake_rules(tmp_path)
    r = run(*_install_args(fake_vault(tmp_path), rules, tmp_path / "state"))
    assert r.returncode == 0, r.stderr
    body = rules.read_text()

    open_idx = body.find(NEW_MARKER_OPEN)
    close_idx = body.find(NEW_MARKER_CLOSE)
    assert open_idx != -1, "new open marker missing"
    assert close_idx != -1, "new close marker missing"
    assert open_idx < close_idx, "open marker must precede close marker"

    between = body[open_idx : close_idx + len(NEW_MARKER_CLOSE)]
    # Must contain the session-bookend instruction keywords
    assert "session-start.sh" in between, \
        "new block must reference session-start.sh"
    assert "session-end.sh" in between, \
        "new block must reference session-end.sh"
    assert "KROKI_SESSION_AUTO" in between, \
        "new block must reference auto-suppression env var"


# ---------------------------------------------------------------------------
# Other Step 2 / infrastructure tests (unchanged)
# ---------------------------------------------------------------------------

def test_creates_state_dir(tmp_path):
    state = tmp_path / "state"
    r = run(*_install_args(fake_vault(tmp_path), fake_rules(tmp_path), state))
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
    r = run(*_install_args(fake_vault(tmp_path), rules, tmp_path / "state"))
    assert r.returncode != 0, "install.sh must fail when Extension-point section missing"
    assert "Extension point" in r.stderr, \
        f"stderr should mention Extension point; got: {r.stderr}"
    # Rules file must not have been mutated
    body = rules.read_text()
    assert NEW_MARKER_OPEN not in body, \
        "Rules file must not be mutated when preflight fails"
    assert OLD_MARKER_OPEN not in body, \
        "Rules file must not be mutated when preflight fails"


# ---------------------------------------------------------------------------
# --uninstall flag tests
# ---------------------------------------------------------------------------

def fake_rules_with_new_marker(tmp: Path) -> Path:
    """Rules file with the new kroki-session INSTALLER block already installed."""
    f = tmp / "session-continuity-with-new.md"
    f.write_text(
        "# Rule: Session Continuity\n\n"
        "At the end of every session involving project work:\n"
        "1. Update `project_session_state.md`\n"
        "2. Update the Obsidian tracker\n"
        "3. Add a session log\n"
        "4. Write a handoff document\n"
        "\n"
        "## Extension point: installer-appended instructions\n\n"
        "Plugins and installers extend session-continuity behavior by appending\n"
        "HTML-comment-bracketed blocks below this paragraph.\n"
        "\n"
        "<!-- INSTALLER: kroki-session -->\n"
        "## Kroki session bookends\n"
        "If the current session involves a project with a `diagrams/` directory:\n"
        "Invoke session-start.sh and session-end.sh with --auto flag.\n"
        "<!-- /INSTALLER: kroki-session -->\n"
    )
    return f


def test_uninstall_removes_new_marker_block(tmp_path):
    """--uninstall removes the kroki-session INSTALLER block from the rules file."""
    rules = fake_rules_with_new_marker(tmp_path)
    r = run("--rules-file", str(rules), "--uninstall")
    assert r.returncode == 0, f"uninstall should exit 0; got: {r.stderr}"
    body = rules.read_text()
    assert NEW_MARKER_OPEN not in body, "new open marker should be removed"
    assert NEW_MARKER_CLOSE not in body, "new close marker should be removed"
    # But rest of the file should remain intact
    assert "## Extension point:" in body, "Extension point section should remain"


def test_uninstall_idempotent_when_marker_absent(tmp_path):
    """--uninstall is idempotent: running when marker is already absent exits 0."""
    rules = fake_rules(tmp_path)
    # File has no kroki-session block
    r = run("--rules-file", str(rules), "--uninstall")
    assert r.returncode == 0, f"uninstall should exit 0 even when marker absent; got: {r.stderr}"
    # File should be unchanged
    original = rules.read_text()
    assert NEW_MARKER_OPEN not in original, "marker should not be present"
    assert OLD_MARKER_OPEN not in original, "old marker should not be present"


def test_uninstall_rules_file_missing_is_noop(tmp_path):
    """--uninstall exits 0 when rules file does not exist (idempotent no-op)."""
    missing_rules = tmp_path / "nonexistent.md"
    r = run("--rules-file", str(missing_rules), "--uninstall")
    assert r.returncode == 0, "uninstall should exit 0 when rules file missing"
    assert "[skip]" in r.stdout, "should log [skip] message"


def test_uninstall_does_not_remove_diagram_schema(tmp_path):
    """--uninstall removes only the INSTALLER block, not the ## diagrams schema row.
    (Persistent schema extensions stay in place per Plan 5a §5.4)."""
    rules_content = (
        "# Rule: Session Continuity\n"
        "## session-log-schema.md content\n"
        "| Section | ... |\n"
        "| `## diagrams` | ... |\n"
        "\n"
        "## Extension point: installer-appended instructions\n\n"
        "<!-- INSTALLER: kroki-session -->\n"
        "block content\n"
        "<!-- /INSTALLER: kroki-session -->\n"
    )
    rules = tmp_path / "rules.md"
    rules.write_text(rules_content)

    r = run("--rules-file", str(rules), "--uninstall")
    assert r.returncode == 0, f"uninstall failed: {r.stderr}"

    body = rules.read_text()
    assert NEW_MARKER_OPEN not in body, "INSTALLER block should be removed"
    # Note: the test verifies the statement "schema row NOT removed" via presence check
    assert "## diagrams" in body, \
        "## diagrams schema row should NOT be removed (persistent by convention)"


def test_uninstall_sed_delimiter_robustness(tmp_path):
    """--uninstall uses | as sed delimiter (not /) to handle <!-- --> safely."""
    rules_content = (
        "# Rules\n"
        "## Extension point\n"
        "<!-- INSTALLER: kroki-session -->\n"
        "If the project has a `diagrams/` directory:\n"
        "invoke session-start.sh / session-end.sh\n"
        "<!-- /INSTALLER: kroki-session -->\n"
    )
    rules = tmp_path / "rules.md"
    rules.write_text(rules_content)

    r = run("--rules-file", str(rules), "--uninstall")
    assert r.returncode == 0, f"uninstall with / in content should succeed; got: {r.stderr}"
    body = rules.read_text()
    assert "<!-- INSTALLER: kroki-session -->" not in body, "marker block should be removed"
    assert "## Extension point" in body, "rest of file should remain"
