"""Unit tests for lib/kroki_container/*."""

import json
import os
import subprocess
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


class TestNetworkAvailable:
    def test_curl_success_returns_true(self):
        from lib.kroki_container import common
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert common.network_available() is True

    def test_curl_failure_returns_false(self):
        from lib.kroki_container import common
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=6)  # dns failure
            assert common.network_available() is False

    def test_curl_timeout_returns_false(self):
        from lib.kroki_container import common
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("curl", 5)):
            assert common.network_available() is False

    def test_curl_missing_returns_false(self):
        from lib.kroki_container import common
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert common.network_available() is False


class TestNotifyAndLog:
    def test_writes_json_line_to_log(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        with patch("subprocess.run"):  # suppress notify-send
            common.notify_and_log("info", "Test", "Body here")
        log = (tmp_path / "notifications.log").read_text().strip().splitlines()
        assert len(log) == 1
        entry = json.loads(log[0])
        assert entry["level"] == "info"
        assert entry["title"] == "Test"
        assert "Body here" in entry["body"]

    def test_includes_suggested_cmds(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        with patch("subprocess.run"):
            common.notify_and_log(
                "warning", "Idle", "Pod idle 2h",
                suggested_cmds=["kroki-watchdog snooze 1h"],
            )
        log = (tmp_path / "notifications.log").read_text().strip().splitlines()
        entry = json.loads(log[0])
        assert "snooze 1h" in entry["body"]
        assert entry["suggested_cmds"] == ["kroki-watchdog snooze 1h"]

    def test_notify_send_missing_is_silent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import common
        with patch("subprocess.run", side_effect=FileNotFoundError):
            common.notify_and_log("info", "Test", "Body")  # must not raise
        log = (tmp_path / "notifications.log").read_text().strip().splitlines()
        assert len(log) == 1  # log write still happened

    def test_log_rotation_at_500_lines(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        log = tmp_path / "notifications.log"
        log.write_text("\n".join(f'{{"ts":{i}}}' for i in range(501)) + "\n")
        from lib.kroki_container import common
        with patch("subprocess.run"):
            common.notify_and_log("info", "Trigger", "body")
        # After rotation: .1 file exists, .log has ≤500 lines
        assert (tmp_path / "notifications.log.1").exists()
        assert len((tmp_path / "notifications.log").read_text().splitlines()) <= 501

    def test_dbus_env_repair(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
        # simulate XDG_RUNTIME_DIR/bus existing
        bus = tmp_path / "bus"
        bus.write_text("")
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        from lib.kroki_container import common
        captured_env = {}
        def fake_run(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return MagicMock(returncode=0)
        with patch("subprocess.run", side_effect=fake_run):
            common.notify_and_log("info", "T", "B")
        assert "DBUS_SESSION_BUS_ADDRESS" in captured_env
        assert str(bus) in captured_env["DBUS_SESSION_BUS_ADDRESS"]


class TestIdleMath:
    def test_idle_seconds_basic(self, monkeypatch):
        from lib.kroki_container import watchdog
        with patch("time.time", return_value=1000):
            assert watchdog.compute_idle_seconds(last_use=700) == 300

    def test_idle_seconds_future_last_use_clamps_to_zero(self, monkeypatch):
        from lib.kroki_container import watchdog
        with patch("time.time", return_value=1000):
            # last_use in the future (clock skew) — don't report negative idle
            assert watchdog.compute_idle_seconds(last_use=1500) == 0


class TestTierFiredState:
    def test_default_all_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import watchdog
        s = watchdog.read_tier_fired_state()
        assert s == {"tier1_fired_at": None, "tier2_fired_at": None}

    def test_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import watchdog
        watchdog.write_tier_fired_state({"tier1_fired_at": 100, "tier2_fired_at": None})
        assert watchdog.read_tier_fired_state() == {"tier1_fired_at": 100, "tier2_fired_at": None}

    def test_reset_if_pod_touched(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import watchdog
        # last_use > tier1_fired_at → reset
        result = watchdog.maybe_reset_tier_state(
            last_use=2000,
            state={"tier1_fired_at": 1000, "tier2_fired_at": None},
        )
        assert result == {"tier1_fired_at": None, "tier2_fired_at": None}

    def test_no_reset_if_never_fired(self, tmp_path, monkeypatch):
        from lib.kroki_container import watchdog
        result = watchdog.maybe_reset_tier_state(
            last_use=2000,
            state={"tier1_fired_at": None, "tier2_fired_at": None},
        )
        assert result == {"tier1_fired_at": None, "tier2_fired_at": None}

    def test_no_reset_if_last_use_older_than_fire(self, tmp_path, monkeypatch):
        from lib.kroki_container import watchdog
        # last_use <= tier1_fired_at → no reset; tier-fire is still "current"
        result = watchdog.maybe_reset_tier_state(
            last_use=500,
            state={"tier1_fired_at": 1000, "tier2_fired_at": None},
        )
        assert result == {"tier1_fired_at": 1000, "tier2_fired_at": None}
