"""Unit tests for lib/kroki_autosave/*."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestConfigLoad:
    def test_missing_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import common
        cfg = common.load_config()
        assert cfg["autosave"]["enabled"] is True
        assert cfg["autosave"]["ttl_days"] == 7
        assert cfg["autosave"]["debounce_seconds"] == 2
        assert cfg["autosave"]["rescan_interval_hours"] == 1
        assert cfg["autosave"]["session_start_scan"] is True
        assert cfg["autosave"]["divergence_stale_threshold_seconds"] == 60
        assert cfg["autosave"]["divergence_freshness_window_seconds"] == 600
        assert cfg["autosave"]["notify_on_delete"] is True
        assert cfg["autosave"]["vault_path"].endswith("Obsidian Vault")

    def test_partial_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / "config.yml").write_text(
            "autosave:\n  ttl_days: 14\n  debounce_seconds: 5\n"
        )
        from lib.kroki_autosave import common
        cfg = common.load_config()
        assert cfg["autosave"]["ttl_days"] == 14
        assert cfg["autosave"]["debounce_seconds"] == 5
        assert cfg["autosave"]["rescan_interval_hours"] == 1
        assert cfg["autosave"]["enabled"] is True

    def test_malformed_yaml_falls_back_to_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / "config.yml").write_text("autosave: : broken:")
        from lib.kroki_autosave import common
        cfg = common.load_config()
        assert cfg["autosave"]["enabled"] is True

    def test_vault_path_tilde_expanded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / "config.yml").write_text(
            "autosave:\n  vault_path: ~/custom-vault\n"
        )
        from lib.kroki_autosave import common
        cfg = common.load_config()
        assert cfg["autosave"]["vault_path"] == os.path.expanduser("~/custom-vault")


class TestStateIO:
    def test_state_dir_default(self, monkeypatch):
        monkeypatch.delenv("KROKI_STATE_DIR", raising=False)
        from lib.kroki_autosave import common
        assert common.state_dir() == Path(os.path.expanduser("~/.kroki-plugin"))

    def test_state_dir_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import common
        assert common.state_dir() == tmp_path

    def test_atomic_write_creates_file(self, tmp_path):
        from lib.kroki_autosave import common
        target = tmp_path / "output.json"
        common.atomic_write(target, '{"k":1}')
        assert target.read_text() == '{"k":1}'

    def test_atomic_write_via_tmp_rename(self, tmp_path):
        from lib.kroki_autosave import common
        target = tmp_path / "output.json"
        common.atomic_write(target, "content")
        assert not (tmp_path / "output.json.tmp").exists()
        assert target.read_text() == "content"

    def test_autosaves_dir_structure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import common
        project_dir = common.project_autosaves_dir("Kroki-Plugin")
        assert project_dir == tmp_path / "autosaves" / "Kroki-Plugin"
        assert project_dir.exists()
        autosaves_root = tmp_path / "autosaves"
        assert oct(autosaves_root.stat().st_mode & 0o777) == "0o700"
