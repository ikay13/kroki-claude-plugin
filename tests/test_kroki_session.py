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

    def test_session_log_missing_skips_embed(self, end_env, monkeypatch, capsys):
        """mode=end proceeds through all steps, skips embed (no stub created)."""
        from lib.kroki_session import end
        pr = end_env["project_root"]
        diag = self._add_and_commit_diagram(pr, "arch", "' Arch\n@startuml\nA\n@enduml\n")
        diag.write_text("' Arch (v2)\n@startuml\nA2\n@enduml\n")

        real_run = subprocess.run
        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if any(s in cmd_str for s in ["pod-health.sh", "render.sh", "a11y-check.sh",
                                            "update-index.sh"]):
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "embed-in-md.sh" in cmd_str:
                raise AssertionError("embed-in-md.sh should NOT be called (no session log)")
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        # No session log file in sessions/
        rc = end.main(project="TestProject", vault_path_override=pr)
        out = capsys.readouterr()
        assert rc == 0
        assert "no session log found" in out.err
        assert "embed skipped" in out.err
        # No stub created
        assert not any((pr / "sessions").iterdir())

    def test_milestone_auto_detect_semver_only(self, end_env, monkeypatch, capsys):
        """v* tag on HEAD triggers milestone; non-semver tags don't."""
        from lib.kroki_session import end
        pr = end_env["project_root"]
        subprocess.run(["git", "-C", str(pr), "tag", "v1.0.0"], check=True)
        subprocess.run(["git", "-C", str(pr), "tag", "last-good"], check=True)
        # Create a session log so embed doesn't warn
        (pr / "sessions" / "2026-04-20-TestProject-session-00.md").write_text(
            "---\nproject: TestProject\n---\n\n# Session 00\n\n## what-was-done\n\nstuff\n"
        )

        snapshot_called_with: list[list[str]] = []
        real_run = subprocess.run

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "pod-health.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "session-snapshot.sh" in cmd_str:
                snapshot_called_with.append([str(c) for c in cmd])
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if any(s in cmd_str for s in ["render.sh", "a11y-check.sh",
                                            "update-index.sh", "embed-in-md.sh"]):
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=pr)
        assert rc == 0
        # session-snapshot.sh was invoked with --milestone-label v1.0.0
        assert len(snapshot_called_with) == 1
        flat = " ".join(snapshot_called_with[0])
        assert "v1.0.0" in flat
        assert "last-good" not in flat

    def test_milestone_skip_sentinel_honored(self, end_env, monkeypatch):
        """If diagrams/milestones/<tag>.skip exists, milestone is not auto-triggered."""
        from lib.kroki_session import end
        pr = end_env["project_root"]
        subprocess.run(["git", "-C", str(pr), "tag", "v1.0.0"], check=True)
        milestones = pr / "diagrams" / "milestones"
        milestones.mkdir()
        (milestones / "v1.0.0.skip").write_text("")

        snapshot_calls = []
        real_run = subprocess.run

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "pod-health.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "session-snapshot.sh" in cmd_str:
                snapshot_calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if any(s in cmd_str for s in ["render.sh", "a11y-check.sh",
                                            "update-index.sh", "embed-in-md.sh"]):
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=pr)
        assert rc == 0
        assert snapshot_calls == []  # no snapshot triggered

    def test_milestone_light_svg_existence_skips(self, end_env, monkeypatch):
        """If milestones/<tag>.light.svg exists (already snapshotted), skip."""
        from lib.kroki_session import end
        pr = end_env["project_root"]
        subprocess.run(["git", "-C", str(pr), "tag", "v1.0.0"], check=True)
        milestones = pr / "diagrams" / "milestones"
        milestones.mkdir()
        (milestones / "v1.0.0.light.svg").write_text("<svg/>")

        snapshot_calls = []
        real_run = subprocess.run

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "pod-health.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "session-snapshot.sh" in cmd_str:
                snapshot_calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if any(s in cmd_str for s in ["render.sh", "a11y-check.sh",
                                            "update-index.sh", "embed-in-md.sh"]):
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        end.main(project="TestProject", vault_path_override=pr)
        assert snapshot_calls == []

    def test_memory_touched_diagrams_deduped(self, end_env, monkeypatch):
        """Memory ## touched-diagrams: existing + new, deduplicated, sorted."""
        from lib.kroki_session import end
        pr = end_env["project_root"]
        # Prime memory with an existing entry
        memory_dir = end_env["tmp_path"] / ".claude" / "projects" / "-home-orin" / "memory"
        (memory_dir / "project_testproject.md").write_text(textwrap.dedent("""\
            ---
            project_name: TestProject
            ---

            ## touched-diagrams

            - old-diagram
            - shared
            """))
        # Session log present
        (pr / "sessions" / "2026-04-20-TestProject-session-00.md").write_text(
            "---\nproject: TestProject\n---\n\n# S00\n\n## what-was-done\n\nx\n"
        )
        diag_shared = self._add_and_commit_diagram(pr, "shared", "' shared\n@startuml\nX\n@enduml\n")
        diag_new = pr / "diagrams" / "fresh.puml"
        diag_shared.write_text("' shared v2\n@startuml\nY\n@enduml\n")
        diag_new.write_text("' fresh\n@startuml\nZ\n@enduml\n")

        real_run = subprocess.run
        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "pod-health.sh" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if any(s in cmd_str for s in ["render.sh", "a11y-check.sh",
                                            "update-index.sh", "embed-in-md.sh"]):
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = end.main(project="TestProject", vault_path_override=pr)
        assert rc == 0

        updated = common.parse_memory("TestProject")
        td = updated["touched_diagrams"]
        assert "old-diagram" in td  # preserved
        assert "shared" in td  # preserved (dedup)
        assert "fresh" in td  # added
        assert td == sorted(set(td))  # sorted, deduplicated


class TestSnapshot:
    """milestone snapshot behaviors — snapshot.py"""

    def _small_svg(self, color: str = "red") -> bytes:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect fill="{color}"/></svg>'.encode()

    @pytest.fixture
    def snapshot_env(self, tmp_path, monkeypatch):
        """Vault + memory scaffold for snapshot tests."""
        pr = tmp_path / "Documents" / "Obsidian Vault" / "TestProject"
        (pr / "diagrams").mkdir(parents=True)
        (tmp_path / ".claude" / "projects" / "-home-orin" / "memory").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        return {"project_root": pr, "tmp_path": tmp_path}

    def test_dual_theme_composite(self, snapshot_env, monkeypatch):
        """Milestone produces <label>.light.svg + <label>.dark.svg + source-list.txt."""
        from lib.kroki_session import snapshot
        pr = snapshot_env["project_root"]
        (pr / "diagrams" / "arch.puml").write_text("' arch\n@startuml\nA\n@enduml\n")
        (pr / "diagrams" / "seq.puml").write_text("' seq\n@startuml\nB\n@enduml\n")

        def fake_render(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "render.sh" in cmd_str:
                # Simulate render.sh creating .light.svg + .dark.svg
                for arg in cmd:
                    if str(arg).endswith(".puml"):
                        src = Path(str(arg))
                        src.with_suffix(".light.svg").write_bytes(self._small_svg("red"))
                        src.with_suffix(".dark.svg").write_bytes(self._small_svg("blue"))
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return subprocess.run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_render)
        rc = snapshot.main(project="TestProject", milestone_label="v1.0.0",
                           vault_path_override=pr)
        assert rc == 0
        milestones = pr / "diagrams" / "milestones"
        assert (milestones / "v1.0.0.light.svg").exists()
        assert (milestones / "v1.0.0.dark.svg").exists()
        assert (milestones / "v1.0.0.source-list.txt").exists()
        # Source list names both source files
        source_list = (milestones / "v1.0.0.source-list.txt").read_text()
        assert "arch.puml" in source_list
        assert "seq.puml" in source_list

    def test_source_list_audit_trail(self, snapshot_env, monkeypatch):
        """source-list.txt records one basename per line."""
        from lib.kroki_session import snapshot
        pr = snapshot_env["project_root"]
        (pr / "diagrams" / "a.puml").write_text("' a\n@startuml\nX\n@enduml\n")

        def fake_render(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "render.sh" in cmd_str:
                for arg in cmd:
                    if str(arg).endswith(".puml"):
                        src = Path(str(arg))
                        src.with_suffix(".light.svg").write_bytes(self._small_svg())
                        src.with_suffix(".dark.svg").write_bytes(self._small_svg())
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return subprocess.run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_render)
        snapshot.main(project="TestProject", milestone_label="alpha", vault_path_override=pr)
        text = (pr / "diagrams" / "milestones" / "alpha.source-list.txt").read_text()
        lines = [l for l in text.splitlines() if l.strip()]
        assert len(lines) == 1

    def test_partial_render_fails_whole_snapshot(self, snapshot_env, monkeypatch):
        """One source fails → overall snapshot fails (milestones are all-or-nothing)."""
        from lib.kroki_session import snapshot
        pr = snapshot_env["project_root"]
        (pr / "diagrams" / "good.puml").write_text("' good\n@startuml\nG\n@enduml\n")
        (pr / "diagrams" / "bad.puml").write_text("' bad\n@startuml\nBAD\n@enduml\n")

        def fake_render(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "render.sh" in cmd_str and "bad.puml" in cmd_str:
                return subprocess.CompletedProcess(cmd, 1, b"", b"render failed")
            if "render.sh" in cmd_str:
                for arg in cmd:
                    if str(arg).endswith(".puml"):
                        src = Path(str(arg))
                        src.with_suffix(".light.svg").write_bytes(self._small_svg())
                        src.with_suffix(".dark.svg").write_bytes(self._small_svg())
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return subprocess.run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_render)
        rc = snapshot.main(project="TestProject", milestone_label="v1.0.0",
                           vault_path_override=pr)
        assert rc == 1
        # No partial output
        assert not (pr / "diagrams" / "milestones" / "v1.0.0.light.svg").exists()

    def test_milestones_index_row_added(self, snapshot_env, monkeypatch):
        """milestones/INDEX.md gains one row per milestone."""
        from lib.kroki_session import snapshot
        pr = snapshot_env["project_root"]
        (pr / "diagrams" / "arch.puml").write_text("' arch\n@startuml\nA\n@enduml\n")

        def fake_render(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "render.sh" in cmd_str:
                for arg in cmd:
                    if str(arg).endswith(".puml"):
                        src = Path(str(arg))
                        src.with_suffix(".light.svg").write_bytes(self._small_svg())
                        src.with_suffix(".dark.svg").write_bytes(self._small_svg())
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return subprocess.run(cmd, **kwargs)

        monkeypatch.setattr("subprocess.run", fake_render)
        snapshot.main(project="TestProject", milestone_label="v0.1.0",
                      vault_path_override=pr)
        idx = (pr / "diagrams" / "milestones" / "INDEX.md").read_text()
        assert "v0.1.0" in idx


class TestLock:
    """Tests for lib.kroki_session.lock — editor lock lifecycle."""

    def test_read_absent_returns_none(self, tmp_path, monkeypatch):
        """U6 — no lock file → None."""
        from lib.kroki_session import lock
        monkeypatch.setattr(lock, "LOCK_PATH", tmp_path / ".active-editor.lock")
        assert lock.read_lock() is None

    def test_read_fresh_returns_dict(self, tmp_path, monkeypatch):
        """Happy path — fresh lock returns parsed dict."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        ts = datetime.now(timezone.utc).isoformat()
        lock_path.write_text(json.dumps({"source_path": "/x/y.puml", "started_at": ts}))

        result = lock.read_lock()
        assert result is not None
        assert result["source_path"] == "/x/y.puml"
        assert result["started_at"] == ts

    def test_read_unknown_keys_tolerated(self, tmp_path, monkeypatch):
        """U19 — extra JSON keys are tolerated (forward compatibility)."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        ts = datetime.now(timezone.utc).isoformat()
        lock_path.write_text(json.dumps({
            "source_path": "/a.puml",
            "started_at": ts,
            "future_field": "tolerated",
            "another": 42,
        }))

        result = lock.read_lock()
        assert result is not None
        assert result["source_path"] == "/a.puml"

    def test_module_importable_and_exports_api(self):
        from lib.kroki_session import lock
        # Core constants
        assert hasattr(lock, "LOCK_PATH")
        assert hasattr(lock, "STALE_THRESHOLD_SECONDS")
        assert lock.STALE_THRESHOLD_SECONDS == 2 * 60 * 60
        # Public functions (stubs OK for now)
        for name in ("write_lock", "read_lock", "clear_lock", "is_stale", "check_editor_lock"):
            assert callable(getattr(lock, name)), f"missing: {name}"
        # Dataclass + exception
        assert hasattr(lock, "LockCheckResult")
        assert hasattr(lock, "LockHeldError")
        assert issubclass(lock.LockHeldError, Exception)

    def test_clear_lock_idempotent(self, tmp_path, monkeypatch):
        """U10 — clear_lock returns False when no lock, True when removed."""
        from lib.kroki_session import lock
        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)

        assert lock.clear_lock() is False  # absent
        lock_path.write_text('{"source_path": null, "started_at": "2026-04-21T00:00:00Z"}')
        assert lock.clear_lock() is True   # present → removed
        assert not lock_path.exists()
        assert lock.clear_lock() is False  # idempotent second call

    def test_is_stale_boundary(self, monkeypatch):
        """U11 — is_stale true at >2h, false at <=2h. Monkeypatched now()."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone, timedelta

        fixed_now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)

        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now if tz else fixed_now.replace(tzinfo=None)

        monkeypatch.setattr(lock, "datetime", FrozenDatetime)

        stale_ts = (fixed_now - timedelta(hours=2, seconds=1)).isoformat()
        fresh_ts = (fixed_now - timedelta(hours=2) + timedelta(seconds=1)).isoformat()

        assert lock.is_stale({"started_at": stale_ts, "source_path": None}) is True
        assert lock.is_stale({"started_at": fresh_ts, "source_path": None}) is False

    def test_is_stale_future_timestamp_not_stale(self, monkeypatch):
        """Extension of U11 — clock-skewed future timestamps are treated as fresh."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone, timedelta

        fixed_now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)

        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now if tz else fixed_now.replace(tzinfo=None)

        monkeypatch.setattr(lock, "datetime", FrozenDatetime)
        future_ts = (fixed_now + timedelta(hours=1)).isoformat()
        assert lock.is_stale({"started_at": future_ts, "source_path": None}) is False

    def test_read_stale_auto_clears(self, tmp_path, monkeypatch, capsys):
        """U7 — stale lock (>2h) unlinks and returns None with stderr log."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone, timedelta

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        stale_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        lock_path.write_text(json.dumps({"source_path": "/s.puml", "started_at": stale_ts}))

        assert lock.read_lock() is None
        assert not lock_path.exists()
        captured = capsys.readouterr()
        assert "stale lock auto-cleared" in captured.err

    def test_read_corrupt_renames_and_returns_none(self, tmp_path, monkeypatch, capsys):
        """U8 — malformed JSON → renamed to .corrupt.<iso-ts>, returns None."""
        from lib.kroki_session import lock

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        lock_path.write_text("this is not valid json {{{")

        assert lock.read_lock() is None
        assert not lock_path.exists()
        corrupt_files = list(tmp_path.glob(".active-editor.lock.corrupt.*"))
        assert len(corrupt_files) == 1
        assert corrupt_files[0].read_text() == "this is not valid json {{{"
        captured = capsys.readouterr()
        assert "corrupt lock moved to" in captured.err

    def test_read_missing_required_keys_also_renames(self, tmp_path, monkeypatch):
        """U8 extension — JSON valid but required keys missing also triggers rename."""
        from lib.kroki_session import lock

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        lock_path.write_text(json.dumps({"something_else": 1}))

        assert lock.read_lock() is None
        assert not lock_path.exists()
        assert list(tmp_path.glob(".active-editor.lock.corrupt.*"))

    def test_read_clock_skew_treats_as_fresh(self, tmp_path, monkeypatch, capsys):
        """U9 — future started_at is tolerated (warns, returns dict)."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone, timedelta

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        lock_path.write_text(json.dumps({"source_path": "/f.puml", "started_at": future_ts}))

        result = lock.read_lock()
        assert result is not None
        assert result["source_path"] == "/f.puml"
        captured = capsys.readouterr()
        assert "clock skew" in captured.err.lower()

    def test_write_creates_valid_schema(self, tmp_path, monkeypatch):
        """U1 — write_lock creates file with required keys."""
        from lib.kroki_session import lock

        lock_path = tmp_path / "kroki-plugin" / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)

        result = lock.write_lock("/abs/path/to/x.puml")
        assert lock_path.exists()
        loaded = json.loads(lock_path.read_text())
        assert loaded["source_path"] == "/abs/path/to/x.puml"
        assert "started_at" in loaded
        assert result == loaded

    def test_write_creates_parent_dir(self, tmp_path, monkeypatch):
        """U5 — ~/.kroki-plugin/ auto-created if missing."""
        from lib.kroki_session import lock

        lock_path = tmp_path / "auto-created-dir" / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        assert not lock_path.parent.exists()
        lock.write_lock(None)
        assert lock_path.parent.is_dir()
        assert lock_path.exists()

    def test_write_raises_when_held_fresh(self, tmp_path, monkeypatch):
        """U2 — fresh held lock raises LockHeldError with held dict attached."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        ts = datetime.now(timezone.utc).isoformat()
        lock_path.write_text(json.dumps({"source_path": "/held.puml", "started_at": ts}))

        with pytest.raises(lock.LockHeldError) as exc_info:
            lock.write_lock("/new.puml")
        assert exc_info.value.held["source_path"] == "/held.puml"
        assert lock_path.exists()  # Original lock still intact.

    def test_write_succeeds_after_stale_autoclean(self, tmp_path, monkeypatch):
        """U3 — stale lock gets auto-cleaned, fresh write lands."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone, timedelta

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        stale_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        lock_path.write_text(json.dumps({"source_path": "/stale.puml", "started_at": stale_ts}))

        result = lock.write_lock("/new.puml")
        loaded = json.loads(lock_path.read_text())
        assert loaded["source_path"] == "/new.puml"
        assert result["source_path"] == "/new.puml"

    def test_write_succeeds_after_corrupt_rename(self, tmp_path, monkeypatch):
        """U4 — corrupt lock renamed out, fresh write lands."""
        from lib.kroki_session import lock

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        lock_path.write_text("not valid json {{{")

        lock.write_lock("/fresh.puml")
        loaded = json.loads(lock_path.read_text())
        assert loaded["source_path"] == "/fresh.puml"
        # Corrupt file preserved for forensics.
        assert list(tmp_path.glob(".active-editor.lock.corrupt.*"))

    def test_check_no_lock(self, tmp_path, monkeypatch):
        """U12 — no lock file → ok / not blocked."""
        from lib.kroki_session import lock

        monkeypatch.setattr(lock, "LOCK_PATH", tmp_path / ".active-editor.lock")
        result = lock.check_editor_lock("/any/source.puml")
        assert result.locked is False
        assert result.blocks_target is False
        assert result.reason == "ok"
        assert result.source_path is None

    def test_check_blank_session_allows_any(self, tmp_path, monkeypatch):
        """U13 — source_path: null lock doesn't block any render target."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        lock_path.write_text(json.dumps({
            "source_path": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }))

        result = lock.check_editor_lock("/any/source.puml")
        assert result.locked is True
        assert result.blocks_target is False
        assert result.reason == "blank-session"
        assert result.source_path is None

    def test_check_source_match_blocks(self, tmp_path, monkeypatch):
        """U14 — exact abspath match → blocked."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        target = str(tmp_path / "target.puml")
        (tmp_path / "target.puml").touch()
        lock_path.write_text(json.dumps({
            "source_path": target,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }))

        result = lock.check_editor_lock(target)
        assert result.locked is True
        assert result.blocks_target is True
        assert result.reason == "locked-on-target"
        assert result.source_path == target

    def test_check_source_differs_allows(self, tmp_path, monkeypatch):
        """U15 — different source → locked but not blocking."""
        from lib.kroki_session import lock
        from datetime import datetime, timezone

        lock_path = tmp_path / ".active-editor.lock"
        monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
        locked_file = str(tmp_path / "locked.puml")
        other_file = str(tmp_path / "other.puml")
        for f in (locked_file, other_file):
            open(f, "w").close()
        lock_path.write_text(json.dumps({
            "source_path": locked_file,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }))

        result = lock.check_editor_lock(other_file)
        assert result.locked is True
        assert result.blocks_target is False
        assert result.reason == "locked-other-file"
        assert result.source_path == locked_file

    def _run_cli(self, monkeypatch, lock_path, *args, input_str: str = ""):
        """Helper: spawn the lock CLI as a subprocess with lock path isolated."""
        env = os.environ.copy()
        env["HOME"] = str(lock_path.parent.parent)  # So Path.home()/.kroki-plugin/... matches lock_path
        proc = subprocess.run(
            [sys.executable, "-m", "lib.kroki_session.lock", *args],
            cwd="/home/orin/kroki-claude-plugin/.worktrees/plan-5c-editor-lock",
            env=env,
            input=input_str,
            capture_output=True,
            text=True,
        )
        return proc

    def test_cli_open_success_and_held(self, tmp_path, monkeypatch):
        """U16 — CLI `open --source X` exits 0; second open exits 3."""
        kroki_dir = tmp_path / ".kroki-plugin"
        kroki_dir.mkdir()
        lock_path = kroki_dir / ".active-editor.lock"

        p1 = self._run_cli(monkeypatch, lock_path, "open", "--source", "/abs/x.puml")
        assert p1.returncode == 0, p1.stderr
        assert lock_path.exists()

        p2 = self._run_cli(monkeypatch, lock_path, "open", "--source", "/abs/y.puml")
        assert p2.returncode == 3, p2.stderr
        assert "held" in p2.stderr.lower() or "lock" in p2.stderr.lower()

    def test_cli_close_idempotent(self, tmp_path, monkeypatch):
        """U17 — `close` exits 0 whether lock exists or not; stdout is JSON of removed lock or empty."""
        kroki_dir = tmp_path / ".kroki-plugin"
        kroki_dir.mkdir()
        lock_path = kroki_dir / ".active-editor.lock"

        # No lock → exit 0, stdout empty.
        p1 = self._run_cli(monkeypatch, lock_path, "close")
        assert p1.returncode == 0
        assert p1.stdout.strip() == ""

        # With lock → exit 0, stdout contains the removed lock's JSON.
        self._run_cli(monkeypatch, lock_path, "open", "--source", "/abs/y.puml")
        p2 = self._run_cli(monkeypatch, lock_path, "close")
        assert p2.returncode == 0
        parsed = json.loads(p2.stdout)
        assert parsed["source_path"] == "/abs/y.puml"

    def test_cli_check_exit_codes(self, tmp_path, monkeypatch):
        """U18 — `check --source X`: 0 for ok / other-file / blank; 2 for on-target."""
        kroki_dir = tmp_path / ".kroki-plugin"
        kroki_dir.mkdir()
        lock_path = kroki_dir / ".active-editor.lock"

        # No lock → exit 0.
        p1 = self._run_cli(monkeypatch, lock_path, "check", "--source", "/x.puml")
        assert p1.returncode == 0

        # Lock on different source → exit 0.
        self._run_cli(monkeypatch, lock_path, "open", "--source", "/a.puml")
        p2 = self._run_cli(monkeypatch, lock_path, "check", "--source", "/b.puml")
        assert p2.returncode == 0

        # Lock on matching source → exit 2.
        p3 = self._run_cli(monkeypatch, lock_path, "check", "--source", "/a.puml")
        assert p3.returncode == 2

        # Blank-session lock → any check source → exit 0.
        self._run_cli(monkeypatch, lock_path, "close")
        self._run_cli(monkeypatch, lock_path, "open")  # blank
        p4 = self._run_cli(monkeypatch, lock_path, "check", "--source", "/anything.puml")
        assert p4.returncode == 0

    def test_common_reexports_check_editor_lock(self):
        """check_editor_lock is importable from common."""
        from lib.kroki_session import common, lock
        assert common.check_editor_lock is lock.check_editor_lock
