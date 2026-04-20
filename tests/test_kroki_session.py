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


class TestStart:
    """mode=start behaviors — start.py"""


class TestEnd:
    """mode=end behaviors — end.py"""


class TestSnapshot:
    """milestone snapshot behaviors — snapshot.py"""
