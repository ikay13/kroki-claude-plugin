"""Unit tests for lib/kroki_container/*."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestConfigLoad:
    def test_missing_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        cfg = common.load_config()
        assert cfg["watchdog"]["enabled"] is True
        assert cfg["watchdog"]["tier1_hours"] == 2
        assert cfg["watchdog"]["tier2_hours"] == 6
        assert cfg["version_check"]["enabled"] is True
        assert cfg["version_check"]["cli_path"].endswith("kroki")

    def test_partial_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / "config.yml").write_text(
            "watchdog:\n  tier1_hours: 4\n"
        )
        from lib.kroki_container import common
        cfg = common.load_config()
        assert cfg["watchdog"]["tier1_hours"] == 4          # overridden
        assert cfg["watchdog"]["tier2_hours"] == 6          # default preserved
        assert cfg["watchdog"]["enabled"] is True           # default preserved
        assert cfg["version_check"]["enabled"] is True      # default preserved

    def test_malformed_yaml_falls_back_to_defaults(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / "config.yml").write_text("watchdog: : broken:")
        from lib.kroki_container import common
        cfg = common.load_config()
        assert cfg["watchdog"]["enabled"] is True           # defaults returned


class TestParseDuration:
    @pytest.mark.parametrize("s,expected", [
        ("30s", 30),
        ("1m", 60),
        ("30m", 1800),
        ("1h", 3600),
        ("2h", 7200),
        ("24h", 86400),
        ("1d", 86400),
        ("7d", 604800),
    ])
    def test_valid_formats(self, s, expected):
        from lib.kroki_container import common
        assert common.parse_duration(s) == expected

    def test_rejects_malformed(self):
        from lib.kroki_container import common
        with pytest.raises(ValueError):
            common.parse_duration("1 hour")
        with pytest.raises(ValueError):
            common.parse_duration("")
        with pytest.raises(ValueError):
            common.parse_duration("5x")


class TestStateIO:
    def test_read_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        assert common.read_state(".nonexistent") is None

    def test_read_write_roundtrip_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        common.write_state(".test.json", {"k": 1})
        assert common.read_state(".test.json") == {"k": 1}

    def test_read_write_roundtrip_epoch(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        common.write_state(".epoch", 1714723200)
        assert common.read_state(".epoch") == 1714723200

    def test_corrupt_json_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".bad.json").write_text("{not json")
        from lib.kroki_container import common
        assert common.read_state(".bad.json") is None

    def test_clear_state(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        common.write_state(".x", 1)
        common.clear_state(".x")
        assert common.read_state(".x") is None

    def test_clear_missing_is_noop(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        common.clear_state(".nonexistent")  # must not raise
