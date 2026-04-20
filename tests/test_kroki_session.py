"""Tests for lib.kroki_session.* modules."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from lib.kroki_session import common
from lib.kroki_session.common import (
    GitState,
    ProjectFolderNotFoundError,
)


def _init_repo(path: Path) -> None:
    """Initialize a git repo at path with initial commit. Helper for tests."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    (path / "README.md").write_text("# Test repo\n")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "initial"], check=True)


class TestCommon:
    """Shared utility behaviors — common.py"""

    def test_vault_paths_convention(self, tmp_path, monkeypatch):
        """Resolves project name to ~/Documents/Obsidian Vault/<Project>/."""
        # Set up a synthetic HOME so we can control the vault folder
        home = tmp_path
        monkeypatch.setenv("HOME", str(home))
        project_dir = home / "Documents" / "Obsidian Vault" / "TestProject"
        project_dir.mkdir(parents=True)

        result = common.vault_paths("TestProject")
        assert result == project_dir

    def test_vault_paths_override_takes_precedence(self, tmp_path):
        """--vault-path override bypasses convention."""
        custom = tmp_path / "custom-vault"
        custom.mkdir()
        result = common.vault_paths("Ignored", override=custom)
        assert result == custom

    def test_vault_paths_override_not_found_raises(self, tmp_path):
        """Override that doesn't exist raises ProjectFolderNotFoundError."""
        missing = tmp_path / "does-not-exist"
        with pytest.raises(ProjectFolderNotFoundError) as exc_info:
            common.vault_paths("Whatever", override=missing)
        assert "does not exist" in str(exc_info.value)

    def test_vault_paths_convention_not_found_raises(self, tmp_path, monkeypatch):
        """Convention path that doesn't exist raises ProjectFolderNotFoundError with bypass hint."""
        monkeypatch.setenv("HOME", str(tmp_path))
        with pytest.raises(ProjectFolderNotFoundError) as exc_info:
            common.vault_paths("NoSuchProject")
        msg = str(exc_info.value)
        assert "obsidian-project-sync.md" in msg
        assert "--vault-path" in msg  # must mention the bypass flag

    def test_atomic_write_creates_file(self, tmp_path):
        target = tmp_path / "output.txt"
        common.atomic_write(target, "hello world\n")
        assert target.read_text() == "hello world\n"

    def test_atomic_write_overwrites_existing(self, tmp_path):
        target = tmp_path / "output.txt"
        target.write_text("old content")
        common.atomic_write(target, "new content")
        assert target.read_text() == "new content"

    def test_atomic_write_no_tmp_leftover_on_success(self, tmp_path):
        target = tmp_path / "output.txt"
        common.atomic_write(target, "content")
        tmp = tmp_path / "output.txt.kroki-tmp"
        assert not tmp.exists()

    def test_extract_purpose_puml(self, tmp_path):
        src = tmp_path / "arch.puml"
        src.write_text("' This is the architecture overview\n@startuml\n")
        assert common.extract_purpose(src) == "This is the architecture overview"

    def test_extract_purpose_mmd(self, tmp_path):
        src = tmp_path / "flow.mmd"
        src.write_text("%% Flow diagram for user signup\ngraph TD\n")
        assert common.extract_purpose(src) == "Flow diagram for user signup"

    def test_extract_purpose_dot(self, tmp_path):
        src = tmp_path / "g.dot"
        src.write_text("// Dependency graph\ndigraph G {}\n")
        assert common.extract_purpose(src) == "Dependency graph"

    def test_extract_purpose_d2(self, tmp_path):
        src = tmp_path / "s.d2"
        src.write_text("# System architecture\nshape: cloud\n")
        assert common.extract_purpose(src) == "System architecture"

    def test_extract_purpose_truncated(self, tmp_path):
        src = tmp_path / "long.puml"
        long_comment = "'" + "x" * 200 + "\n@startuml"
        src.write_text(long_comment)
        result = common.extract_purpose(src)
        assert len(result) <= 120

    def test_extract_purpose_no_comment(self, tmp_path):
        src = tmp_path / "no-comment.puml"
        src.write_text("@startuml\nfoo -> bar\n")
        assert common.extract_purpose(src) == ""

    @pytest.fixture
    def memory_fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "session-fixtures"

    def test_parse_memory_complete(self, tmp_path, monkeypatch, memory_fixtures_dir):
        """Fully populated memory file returns all expected fields."""
        memory_dir = tmp_path / ".claude" / "projects" / "-home-orin" / "memory"
        memory_dir.mkdir(parents=True)
        target = memory_dir / "project_testproject.md"
        target.write_text((memory_fixtures_dir / "memory-complete.md").read_text())
        monkeypatch.setenv("HOME", str(tmp_path))

        result = common.parse_memory("TestProject")
        assert result["project_name"] == "TestProject"
        assert result["latest_session_log"] == "sessions/2026-04-20-TestProject-session-03.md"
        assert result["touched_diagrams"] == ["arch-overview", "seq-login-flow"]
        assert len(result["next_steps"]) == 3
        assert "Write tests for foo" in result["next_steps"][0]
        assert result["current_status"].startswith("Phase 1 complete")

    def test_parse_memory_minimal(self, tmp_path, monkeypatch, memory_fixtures_dir):
        """Memory with only frontmatter returns empty body sections."""
        memory_dir = tmp_path / ".claude" / "projects" / "-home-orin" / "memory"
        memory_dir.mkdir(parents=True)
        target = memory_dir / "project_testproject.md"
        target.write_text((memory_fixtures_dir / "memory-minimal.md").read_text())
        monkeypatch.setenv("HOME", str(tmp_path))

        result = common.parse_memory("TestProject")
        assert result["project_name"] == "TestProject"
        assert result.get("touched_diagrams", []) == []
        assert result.get("next_steps", []) == []

    def test_parse_memory_missing_file(self, tmp_path, monkeypatch):
        """Missing memory file returns empty dict, no exception."""
        monkeypatch.setenv("HOME", str(tmp_path))
        result = common.parse_memory("NonExistent")
        assert result == {}

    def test_parse_memory_malformed_returns_partial(self, tmp_path, monkeypatch, memory_fixtures_dir, capsys):
        """Malformed frontmatter logs warning, returns best-effort dict."""
        memory_dir = tmp_path / ".claude" / "projects" / "-home-orin" / "memory"
        memory_dir.mkdir(parents=True)
        target = memory_dir / "project_testproject.md"
        target.write_text((memory_fixtures_dir / "memory-malformed.md").read_text())
        monkeypatch.setenv("HOME", str(tmp_path))

        result = common.parse_memory("TestProject")
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower() or "malformed" in captured.err.lower()
        # Best-effort: we got something; don't require specific fields
        assert isinstance(result, dict)

    def test_write_memory_roundtrip(self, tmp_path, monkeypatch, memory_fixtures_dir):
        """write_memory after parse_memory preserves frontmatter + body; updates last_updated."""
        memory_dir = tmp_path / ".claude" / "projects" / "-home-orin" / "memory"
        memory_dir.mkdir(parents=True)
        target = memory_dir / "project_testproject.md"
        target.write_text((memory_fixtures_dir / "memory-complete.md").read_text())
        monkeypatch.setenv("HOME", str(tmp_path))

        data = common.parse_memory("TestProject")
        data["touched_diagrams"] = ["arch-overview", "seq-login-flow", "new-diagram"]
        common.write_memory("TestProject", data)

        reread = common.parse_memory("TestProject")
        assert "new-diagram" in reread["touched_diagrams"]
        # Core frontmatter preserved
        assert reread["project_name"] == "TestProject"

    def test_write_memory_snake_case_filename(self, tmp_path, monkeypatch):
        """Project name converts to snake_case for filename."""
        memory_dir = tmp_path / ".claude" / "projects" / "-home-orin" / "memory"
        memory_dir.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))

        common.write_memory("My-Fancy Project", {"project_name": "My-Fancy Project",
                                                   "touched_diagrams": []})
        assert (memory_dir / "project_my_fancy_project.md").exists()

    def test_git_state_check_ok(self, tmp_path, monkeypatch):
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert common.git_state_check() == GitState.OK

    def test_git_state_check_detached(self, tmp_path, monkeypatch):
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        # Detach HEAD
        sha = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "-C", str(tmp_path), "checkout", "-q", sha], check=True)
        assert common.git_state_check() == GitState.DETACHED

    def test_git_state_check_no_repo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert common.git_state_check() == GitState.NO_REPO

    def test_git_state_check_merge_in_progress(self, tmp_path, monkeypatch):
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        # Create conflicting branches
        subprocess.run(["git", "-C", str(tmp_path), "checkout", "-q", "-b", "branch1"], check=True)
        (tmp_path / "conflict.txt").write_text("branch1\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", "conflict.txt"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "b1"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "checkout", "-q", "main"], check=True)
        (tmp_path / "conflict.txt").write_text("main\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", "conflict.txt"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "main"], check=True)
        # Attempt merge (will conflict)
        result = subprocess.run(["git", "-C", str(tmp_path), "merge", "branch1"],
                                capture_output=True)
        # merge should fail with conflict; MERGE_HEAD should exist
        assert (tmp_path / ".git" / "MERGE_HEAD").exists()
        assert common.git_state_check() == GitState.MERGE

    def test_git_detect_changes_modified_new_deleted(self, tmp_path, monkeypatch):
        _init_repo(tmp_path)
        diagrams = tmp_path / "diagrams"
        diagrams.mkdir()
        # Commit an initial diagram
        (diagrams / "arch.puml").write_text("' Initial\n@startuml\nA\n@enduml\n")
        (diagrams / "seq.puml").write_text("' Seq\n@startuml\nB\n@enduml\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", "diagrams/"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "diagrams"], check=True)

        # Modify one, add a new one, delete one
        (diagrams / "arch.puml").write_text("' Modified\n@startuml\nA2\n@enduml\n")
        (diagrams / "new-one.puml").write_text("' New\n@startuml\nC\n@enduml\n")
        (diagrams / "seq.puml").unlink()

        monkeypatch.chdir(tmp_path)
        result = common.git_detect_changes(diagrams)
        assert "arch.puml" in [p.name for p in result["modified"]]
        assert "new-one.puml" in [p.name for p in result["new"]]
        assert "seq.puml" in [p.name for p in result["deleted"]]

    def test_git_detect_changes_empty_when_clean(self, tmp_path, monkeypatch):
        _init_repo(tmp_path)
        diagrams = tmp_path / "diagrams"
        diagrams.mkdir()
        (diagrams / "a.puml").write_text("' test\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", "diagrams/"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "c"], check=True)
        monkeypatch.chdir(tmp_path)
        result = common.git_detect_changes(diagrams)
        assert result["modified"] == []
        assert result["new"] == []
        assert result["deleted"] == []

    def test_git_detect_tags_on_head_semver_only(self, tmp_path, monkeypatch):
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        subprocess.run(["git", "-C", str(tmp_path), "tag", "v1.0.0"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "tag", "wip-backup"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "tag", "v2.0.0-rc1"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "tag", "last-good"], check=True)

        result = common.git_detect_tags_on_head("v*")
        assert "v1.0.0" in result
        assert "v2.0.0-rc1" in result
        assert "wip-backup" not in result
        assert "last-good" not in result

    def test_git_detect_tags_on_head_empty(self, tmp_path, monkeypatch):
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = common.git_detect_tags_on_head("v*")
        assert result == []

    def test_resolve_session_log_from_memory(self, tmp_path, monkeypatch):
        """Primary path: use memory's latest_session_log frontmatter field."""
        # Set up memory
        memory_dir = tmp_path / ".claude" / "projects" / "-home-orin" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "project_testproject.md").write_text(textwrap.dedent("""\
            ---
            project_name: TestProject
            latest_session_log: sessions/2026-04-20-TestProject-session-03.md
            ---
            """))
        # Set up vault
        vault = tmp_path / "Documents" / "Obsidian Vault" / "TestProject"
        sessions_dir = vault / "sessions"
        sessions_dir.mkdir(parents=True)
        target = sessions_dir / "2026-04-20-TestProject-session-03.md"
        target.write_text("# Session 03\n")
        monkeypatch.setenv("HOME", str(tmp_path))

        result = common.resolve_session_log("TestProject", which="latest")
        assert result == target

    def test_resolve_session_log_glob_fallback(self, tmp_path, monkeypatch):
        """Fallback: if memory absent, glob + sort by NN."""
        vault = tmp_path / "Documents" / "Obsidian Vault" / "TestProject"
        sessions_dir = vault / "sessions"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "2026-04-17-TestProject-session-00.md").write_text("# 00\n")
        (sessions_dir / "2026-04-18-TestProject-session-01.md").write_text("# 01\n")
        (sessions_dir / "2026-04-20-TestProject-session-02.md").write_text("# 02\n")
        monkeypatch.setenv("HOME", str(tmp_path))

        latest = common.resolve_session_log("TestProject", which="latest")
        assert latest.name == "2026-04-20-TestProject-session-02.md"

        prev = common.resolve_session_log("TestProject", which="previous")
        assert prev.name == "2026-04-18-TestProject-session-01.md"

    def test_resolve_session_log_none_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert common.resolve_session_log("NoSuchProject", which="latest") is None

    def test_parse_session_log_with_diagrams(self, memory_fixtures_dir):
        path = memory_fixtures_dir / "session-log-with-diagrams.md"
        result = common.parse_session_log(path)
        assert result["frontmatter"]["project"] == "TestProject"
        assert result["frontmatter"]["session_nn"] == "3"
        # Each diagram embed block produces one "diagram" entry (by basename)
        assert "arch-overview" in result["diagrams"]
        assert "seq-login-flow" in result["diagrams"]

    def test_parse_session_log_without_diagrams(self, memory_fixtures_dir):
        path = memory_fixtures_dir / "session-log-without-diagrams.md"
        result = common.parse_session_log(path)
        assert result["diagrams"] == []

    def test_parse_session_log_malformed(self, memory_fixtures_dir, capsys):
        path = memory_fixtures_dir / "session-log-malformed.md"
        result = common.parse_session_log(path)
        # Best-effort: should not crash; may return empty dicts/lists
        assert isinstance(result.get("diagrams", []), list)

    def test_write_session_log_section_creates_when_absent(self, tmp_path):
        target = tmp_path / "session.md"
        target.write_text(textwrap.dedent("""\
            # Session 01

            ## session-goal

            A goal.

            ## what-was-done

            Things.
            """))
        common.write_session_log_section(target, "## diagrams", "new content here\n")
        text = target.read_text()
        assert "## diagrams" in text
        assert "new content here" in text
        # New section should appear at end (no subsequent ## before it)
        assert text.rstrip().endswith("new content here")

    def test_write_session_log_section_replaces_existing(self, tmp_path):
        target = tmp_path / "session.md"
        target.write_text(textwrap.dedent("""\
            # Session 01

            ## diagrams

            old embed content

            ## artifacts-produced

            some-file.py
            """))
        common.write_session_log_section(target, "## diagrams", "new embed content\n")
        text = target.read_text()
        assert "old embed content" not in text
        assert "new embed content" in text
        assert "## artifacts-produced" in text  # preserved
        assert "some-file.py" in text

    def test_write_session_log_section_idempotent(self, tmp_path):
        target = tmp_path / "session.md"
        target.write_text("# Session 01\n\n## what-was-done\n\nThings.\n")
        common.write_session_log_section(target, "## diagrams", "content-v1\n")
        first = target.read_text()
        common.write_session_log_section(target, "## diagrams", "content-v1\n")
        second = target.read_text()
        assert first == second  # same content → same file

    def test_write_session_log_section_dedupes_on_corruption(self, tmp_path):
        """If ## diagrams appears twice (buggy prior run), write replaces all and leaves one."""
        target = tmp_path / "session.md"
        target.write_text(textwrap.dedent("""\
            # Session 01

            ## diagrams

            dup1

            ## what-was-done

            Stuff.

            ## diagrams

            dup2
            """))
        common.write_session_log_section(target, "## diagrams", "canonical\n")
        text = target.read_text()
        # Exactly one ## diagrams
        assert text.count("\n## diagrams") == 1
        assert "dup1" not in text
        assert "dup2" not in text
        assert "canonical" in text
        # what-was-done preserved
        assert "## what-was-done" in text
        assert "Stuff." in text

    def test_parse_index_summary_parses_rows(self, tmp_path):
        """Parse INDEX.md table rows into ReferenceEntry list."""
        index = tmp_path / "INDEX.md"
        index.write_text(textwrap.dedent("""\
            # Diagrams

            ## arch

            | File | Purpose | Updated | Source |
            |------|---------|---------|--------|
            | [[arch-overview.svg|Arch Overview]] | System overview | 2026-04-20 | arch-overview.puml |

            ## seq

            | File | Purpose | Updated | Source |
            |------|---------|---------|--------|
            | [[seq-login.svg|Seq Login]] | Login sequence flow | 2026-04-19 | seq-login.puml |
            """))
        result = common.parse_index_summary(index)
        assert len(result) == 2
        assert any(e["basename"] == "arch-overview" and e["purpose"] == "System overview"
                   and e["last_updated"] == "2026-04-20" for e in result)
        assert any(e["basename"] == "seq-login" for e in result)

    def test_parse_index_summary_missing_file(self, tmp_path):
        """Missing INDEX.md returns empty list, no error."""
        result = common.parse_index_summary(tmp_path / "missing.md")
        assert result == []


class TestStart:
    """mode=start behaviors — start.py"""

    @pytest.fixture
    def start_env(self, tmp_path, monkeypatch):
        """Minimal vault + memory setup for start.py tests."""
        vault = tmp_path / "Documents" / "Obsidian Vault" / "TestProject"
        (vault / "diagrams").mkdir(parents=True)
        (vault / "sessions").mkdir()
        memory_dir = tmp_path / ".claude" / "projects" / "-home-orin" / "memory"
        memory_dir.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        return {"vault": vault, "memory_dir": memory_dir}

    def test_auto_flag_suppresses_when_env_var_set(self, start_env, monkeypatch, capsys):
        """--auto + KROKI_SESSION_AUTO=0 → exit 0 silent."""
        from lib.kroki_session import start
        monkeypatch.setenv("KROKI_SESSION_AUTO", "0")
        rc = start.main(project="TestProject", auto=True)
        out = capsys.readouterr()
        assert rc == 0
        assert out.out == ""
        assert out.err == ""

    def test_explicit_ignores_env_var(self, start_env, monkeypatch, capsys):
        """No --auto + KROKI_SESSION_AUTO=0 → proceeds normally (hits activity gate)."""
        from lib.kroki_session import start
        monkeypatch.setenv("KROKI_SESSION_AUTO", "0")
        rc = start.main(project="TestProject", auto=False)
        # No memory, no prev session → activity gate skips
        out = capsys.readouterr()
        assert rc == 0
        assert "skipped" in out.err.lower()  # explicit skip message

    def test_activity_gate_skips_no_diagrams_dir(self, tmp_path, monkeypatch, capsys):
        from lib.kroki_session import start
        vault = tmp_path / "Documents" / "Obsidian Vault" / "TestProject"
        vault.mkdir(parents=True)  # note: no diagrams subdir
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = start.main(project="TestProject", auto=False)
        out = capsys.readouterr()
        assert rc == 0
        assert "no diagrams/" in out.err

    def test_activity_gate_skips_no_prior_activity(self, start_env, capsys):
        """diagrams/ exists but no memory touched_diagrams + no prev session diagrams → skip."""
        from lib.kroki_session import start
        rc = start.main(project="TestProject", auto=False)
        out = capsys.readouterr()
        assert rc == 0
        assert "no diagram activity" in out.err

    def test_activity_gate_fires_on_prior_memory_diagrams(self, start_env, capsys):
        """Memory has touched_diagrams → activity gate passes, payload emitted."""
        from lib.kroki_session import start
        (start_env["memory_dir"] / "project_testproject.md").write_text(textwrap.dedent("""\
            ---
            project_name: TestProject
            ---

            ## touched-diagrams

            - arch-overview

            ## next-steps

            - Review
            """))
        rc = start.main(project="TestProject", auto=False)
        out = capsys.readouterr()
        assert rc == 0
        # stdout has JSON payload
        assert out.out.strip().startswith("{")
        payload = json.loads(out.out)
        assert payload["mode"] == "start"
        assert payload["project"] == "TestProject"
        assert "arch-overview" in payload.get("loaded_diagrams", []) or payload.get("loaded_diagrams") == []
        # payload always has all keys (may be empty lists)
        for key in ("mode", "project", "vault_dir", "loaded_diagrams",
                    "reference_summary", "last_next_steps"):
            assert key in payload

    def test_vault_not_found_exits_zero_with_stderr(self, tmp_path, monkeypatch, capsys):
        """mode=start: ProjectFolderNotFoundError logs but doesn't fail."""
        from lib.kroki_session import start
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = start.main(project="NoSuchProject", auto=False)
        out = capsys.readouterr()
        assert rc == 0
        assert "kroki-session:" in out.err


class TestEnd:
    """mode=end behaviors — end.py"""

    @pytest.fixture
    def end_env(self, tmp_path, monkeypatch):
        """Synthetic git-initialized vault with diagrams/ subdir."""
        project_root = tmp_path / "Documents" / "Obsidian Vault" / "TestProject"
        _init_repo(project_root.parent.parent)  # init at HOME/Documents/Obsidian Vault
        # Actually simpler: init in the project folder itself
        return self._setup_project(tmp_path, monkeypatch)

    def _setup_project(self, tmp_path, monkeypatch):
        project_root = tmp_path / "Documents" / "Obsidian Vault" / "TestProject"
        project_root.mkdir(parents=True)
        _init_repo(project_root)
        (project_root / "diagrams").mkdir()
        (project_root / "sessions").mkdir()
        (tmp_path / ".claude" / "projects" / "-home-orin" / "memory").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(project_root)
        return {"project_root": project_root, "tmp_path": tmp_path}

    def test_end_auto_flag_suppresses_when_env_var_set(self, end_env, monkeypatch, capsys):
        from lib.kroki_session import end
        monkeypatch.setenv("KROKI_SESSION_AUTO", "0")
        rc = end.main(project="TestProject", auto=True, vault_path_override=end_env["project_root"])
        out = capsys.readouterr()
        assert rc == 0
        assert out.out == ""
        assert out.err == ""

    def test_pod_preflight_failure_exits_two(self, end_env, monkeypatch, capsys):
        """pod-health.sh non-zero → exit 2."""
        from lib.kroki_session import end

        def fake_run(cmd, **kwargs):
            if "pod-health.sh" in str(cmd):
                return subprocess.CompletedProcess(cmd, returncode=1, stdout=b"", stderr=b"pod down")
            return subprocess.run(cmd, **kwargs)  # passthrough

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=end_env["project_root"])
        assert rc == 2
        out = capsys.readouterr()
        assert "pod" in out.err.lower()

    def test_pod_preflight_success_continues(self, end_env, monkeypatch):
        from lib.kroki_session import end

        real_run = subprocess.run
        def fake_run(cmd, **kwargs):
            if "pod-health.sh" in str(cmd):
                return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")
            # For all other commands (including git), use the real subprocess.run
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=end_env["project_root"])
        assert rc == 0  # clean vault with no diagram work → exit 0

    def test_detached_head_skips_gracefully(self, end_env, monkeypatch, capsys):
        from lib.kroki_session import end
        from unittest.mock import Mock

        # Detach HEAD
        sha = subprocess.run(["git", "-C", str(end_env["project_root"]), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "-C", str(end_env["project_root"]), "checkout", "-q", sha], check=True)

        real_run = subprocess.run
        def fake_run(cmd, **kwargs):
            if "pod-health.sh" in str(cmd):
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            # For all other commands (including git), use the real subprocess.run
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=end_env["project_root"])
        out = capsys.readouterr()
        assert rc == 0
        assert "detached HEAD" in out.err

    def test_no_repo_skips_gracefully(self, tmp_path, monkeypatch, capsys):
        """NO_REPO → skip with stderr note, exit 0."""
        from lib.kroki_session import end
        project_root = tmp_path / "Documents" / "Obsidian Vault" / "NoRepoProject"
        (project_root / "diagrams").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(project_root)

        real_run = subprocess.run
        def fake_run(cmd, **kwargs):
            if "pod-health.sh" in str(cmd):
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            # For all other commands (including git), use the real subprocess.run
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="NoRepoProject", vault_path_override=project_root)
        out = capsys.readouterr()
        assert rc == 0
        assert "no git repo" in out.err.lower() or "no_repo" in out.err.lower()

    def test_no_changes_exits_zero_silent(self, end_env, monkeypatch, capsys):
        """Clean repo, no diagram work, no tags → exit 0 with skip stderr."""
        from lib.kroki_session import end

        real_run = subprocess.run
        def fake_run(cmd, **kwargs):
            if "pod-health.sh" in str(cmd):
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            # For all other commands (including git), use the real subprocess.run
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=end_env["project_root"])
        out = capsys.readouterr()
        assert rc == 0
        assert "no diagram activity" in out.err or "skipped" in out.err.lower()

    def _add_and_commit_diagram(self, project_root, basename, content):
        diag = project_root / "diagrams" / f"{basename}.puml"
        diag.write_text(content)
        subprocess.run(["git", "-C", str(project_root), "add", "diagrams/"], check=True)
        subprocess.run(["git", "-C", str(project_root), "commit", "-q", "-m", f"add {basename}"], check=True)
        return diag

    def test_per_diagram_failure_isolated(self, end_env, monkeypatch, capsys):
        """One source fails render, another succeeds; successes count incremented."""
        from lib.kroki_session import end
        pr = end_env["project_root"]
        diag1 = self._add_and_commit_diagram(pr, "good", "' Good\n@startuml\nA\n@enduml\n")
        diag2 = self._add_and_commit_diagram(pr, "bad", "' Bad\n@startuml\nB\n@enduml\n")

        # Modify both
        diag1.write_text("' Good (v2)\n@startuml\nA2\n@enduml\n")
        diag2.write_text("' Bad (v2)\n@startuml\nSYNTAX ERROR\n@enduml\n")

        calls: list[list[str]] = []
        real_run = subprocess.run

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            calls.append(list(str(c) for c in cmd))
            if "pod-health.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "render.sh" in cmd_str:
                if "bad.puml" in cmd_str:
                    return subprocess.CompletedProcess(cmd, 1, b"", b"syntax error")
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "a11y-check.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "update-index.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=pr)
        out = capsys.readouterr()
        # rc should be 0 — partial success is OK (1 of 2 rendered)
        assert rc == 0
        assert "1/2" in out.err or "rendered: 1" in out.err

    def test_all_renders_fail_exits_one(self, end_env, monkeypatch):
        from lib.kroki_session import end
        pr = end_env["project_root"]
        diag = self._add_and_commit_diagram(pr, "one", "' One\n@startuml\nA\n@enduml\n")
        diag.write_text("' One (v2)\n@startuml\nBAD\n@enduml\n")

        real_run = subprocess.run

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "pod-health.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "render.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 1, b"", b"render failed")
            if "update-index.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=pr)
        assert rc == 1


class TestSnapshot:
    """milestone snapshot behaviors — snapshot.py"""
