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


class TestStart:
    """mode=start behaviors — start.py"""


class TestEnd:
    """mode=end behaviors — end.py"""


class TestSnapshot:
    """milestone snapshot behaviors — snapshot.py"""
