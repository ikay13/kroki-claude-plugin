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


class TestInferProjectFromPath:
    def test_diagram_path(self, tmp_path):
        from lib.kroki_autosave import common
        vault = tmp_path / "Vault"
        src = vault / "Kroki-Plugin" / "diagrams" / "arch-foo.puml"
        src.parent.mkdir(parents=True)
        src.write_text("a")
        assert common.infer_project_from_path(src, vault) == "Kroki-Plugin"

    def test_session_path(self, tmp_path):
        from lib.kroki_autosave import common
        vault = tmp_path / "Vault"
        src = vault / "MSP" / "sessions" / "2026-04-21-MSP-session-00.md"
        src.parent.mkdir(parents=True)
        src.write_text("a")
        assert common.infer_project_from_path(src, vault) == "MSP"

    def test_non_vault_path_raises(self, tmp_path):
        from lib.kroki_autosave import common
        vault = tmp_path / "Vault"
        src = tmp_path / "elsewhere" / "foo.puml"
        src.parent.mkdir(parents=True)
        src.write_text("a")
        with pytest.raises(ValueError):
            common.infer_project_from_path(src, vault)


class TestProjectGlob:
    def test_typical_vault_layout(self, tmp_path):
        from lib.kroki_autosave import common
        vault = tmp_path / "Vault"
        for project in ["Kroki-Plugin", "MSP", "FDLE-Pipeline"]:
            (vault / project / "diagrams").mkdir(parents=True)
            (vault / project / "sessions").mkdir(parents=True)
        projects, dirs = common.discover_projects(vault)
        assert set(projects) == {"Kroki-Plugin", "MSP", "FDLE-Pipeline"}
        assert len(dirs) == 6  # 3 projects x 2 dirs

    def test_no_autosave_marker_filters(self, tmp_path):
        from lib.kroki_autosave import common
        vault = tmp_path / "Vault"
        for project in ["Kroki-Plugin", "MSP"]:
            (vault / project / "diagrams").mkdir(parents=True)
            (vault / project / "sessions").mkdir(parents=True)
        (vault / "MSP" / ".no-autosave").write_text("")
        projects, _ = common.discover_projects(vault)
        assert set(projects) == {"Kroki-Plugin"}

    def test_vault_missing_returns_empty(self, tmp_path):
        from lib.kroki_autosave import common
        vault = tmp_path / "NoSuchVault"
        projects, dirs = common.discover_projects(vault)
        assert projects == []
        assert dirs == []

    def test_non_directory_entries_skipped(self, tmp_path):
        from lib.kroki_autosave import common
        vault = tmp_path / "Vault"
        vault.mkdir()
        (vault / "notes.md").write_text("a")
        (vault / "Kroki-Plugin" / "diagrams").mkdir(parents=True)
        (vault / "Kroki-Plugin" / "sessions").mkdir(parents=True)
        projects, _ = common.discover_projects(vault)
        assert projects == ["Kroki-Plugin"]


class TestNotifyAndLog:
    def test_notify_invokes_notify_send(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import common
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0)

        monkeypatch.setattr("subprocess.run", fake_run)
        common.notify_and_log("title", "body")
        assert len(calls) == 1
        assert calls[0][0] == "notify-send"

    def test_notify_logs_to_notifications_log(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import common
        monkeypatch.setattr("subprocess.run", lambda *a, **k: MagicMock(returncode=0))
        common.notify_and_log("title", "body")
        log = (tmp_path / "notifications.log").read_text()
        assert "title" in log and "body" in log

    def test_notify_subprocess_failure_does_not_raise(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import common
        def raise_error(*a, **k):
            raise FileNotFoundError("notify-send not installed")
        monkeypatch.setattr("subprocess.run", raise_error)
        common.notify_and_log("title", "body")
        assert (tmp_path / "notifications.log").exists()
