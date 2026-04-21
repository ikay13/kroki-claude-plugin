"""Unit tests for lib/kroki_container/*."""

import json
import os
import subprocess
import tempfile
import time
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


class TestWatchdogCycle:
    def _setup(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        # Touch .last-use with an old timestamp — watchdog reads this
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 10000))

    def test_disabled_in_config_is_noop(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / "config.yml").write_text("watchdog:\n  enabled: false\n")
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 100000))  # very old
        from lib.kroki_container import watchdog
        with patch("subprocess.run") as mock_run:
            assert watchdog.cycle() == 0
        # No notify-send, no kroki.sh down
        calls = [call for call in mock_run.call_args_list
                 if len(call[0]) > 0 and (
                     call[0][0][0] in ("notify-send", "kroki.sh") or
                     "kroki.sh" in " ".join(str(a) for a in call[0][0]))]
        assert len(calls) == 0

    def test_editor_lock_held_defers_silently(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 100000))
        # simulate active editor lock — not stale
        lock_payload = {
            "source_path": "/x/y.puml",
            "started_at": int(time.time()),
            "pid": 12345,
            "share_url": "http://localhost:8017/#abc",
        }
        (tmp_path / ".active-editor.lock").write_text(json.dumps(lock_payload))
        from lib.kroki_container import watchdog
        with patch("lib.kroki_container.watchdog.read_lock", return_value=lock_payload), \
             patch("lib.kroki_container.watchdog.is_stale", return_value=False), \
             patch("subprocess.run") as mock_run:
            assert watchdog.cycle() == 0
        # No kroki.sh down invoked
        assert not any("kroki.sh" in " ".join(str(a) for a in call[0][0])
                       for call in mock_run.call_args_list)

    def test_upgrade_in_progress_defers(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 100000))
        (tmp_path / ".upgrade-in-progress").write_text(f"{os.getpid()} {int(time.time())}")
        from lib.kroki_container import watchdog
        with patch("lib.kroki_container.watchdog.read_lock", return_value=None), \
             patch("subprocess.run") as mock_run:
            assert watchdog.cycle() == 0
        assert not any("kroki.sh" in " ".join(str(a) for a in call[0][0])
                       for call in mock_run.call_args_list)

    def test_snooze_active_defers(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 100000))
        snooze_until = int(time.time()) + 3600  # 1h in future
        (tmp_path / ".watchdog-snooze-until").write_text(str(snooze_until))
        from lib.kroki_container import watchdog
        with patch("lib.kroki_container.watchdog.read_lock", return_value=None), \
             patch("subprocess.run") as mock_run:
            assert watchdog.cycle() == 0

    def test_snooze_expired_clears_file(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 100))  # recent
        (tmp_path / ".watchdog-snooze-until").write_text(str(int(time.time()) - 60))  # expired
        from lib.kroki_container import watchdog
        with patch("lib.kroki_container.watchdog.read_lock", return_value=None), \
             patch("subprocess.run"):
            watchdog.cycle()
        assert not (tmp_path / ".watchdog-snooze-until").exists()

    def test_tier1_fires_at_threshold(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 2 * 3600 - 60))  # ~2h1m idle
        from lib.kroki_container import watchdog
        with patch("lib.kroki_container.watchdog.read_lock", return_value=None), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            watchdog.cycle()
        # tier-fired state should record tier1
        state = json.loads((tmp_path / ".watchdog-tier-fired.json").read_text())
        assert state["tier1_fired_at"] is not None
        assert state["tier2_fired_at"] is None
        # notify-send should have been called
        assert any("notify-send" in call[0][0][0]
                   for call in mock_run.call_args_list)

    def test_tier1_dedup_second_cycle_does_not_refire(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        last_use = int(time.time()) - 3 * 3600
        (tmp_path / ".last-use").write_text(str(last_use))
        # tier1 already fired 30 min ago
        (tmp_path / ".watchdog-tier-fired.json").write_text(
            json.dumps({"tier1_fired_at": int(time.time()) - 1800, "tier2_fired_at": None})
        )
        from lib.kroki_container import watchdog
        with patch("lib.kroki_container.watchdog.read_lock", return_value=None), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            watchdog.cycle()
        # No new notify-send in this cycle
        notify_calls = [c for c in mock_run.call_args_list
                        if "notify-send" in c[0][0][0]]
        assert len(notify_calls) == 0

    def test_tier2_fires_and_stops_pod(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 6 * 3600 - 300))  # ~6h5m
        from lib.kroki_container import watchdog
        with patch("lib.kroki_container.watchdog.read_lock", return_value=None), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            watchdog.cycle()
        # kroki.sh down invoked
        assert any("kroki.sh" in " ".join(str(a) for a in c[0][0]) and "down" in str(c[0][0])
                   for c in mock_run.call_args_list)
        # tier2 recorded
        state = json.loads((tmp_path / ".watchdog-tier-fired.json").read_text())
        assert state["tier2_fired_at"] is not None


class TestWatchdogSubcommands:
    def test_snooze_writes_file(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import watchdog
        assert watchdog.cmd_snooze("1h") == 0
        raw = (tmp_path / ".watchdog-snooze-until").read_text().strip()
        until = int(raw)
        assert until >= int(time.time()) + 3500  # allow ~100s slop

    def test_ignore_equals_snooze_24h(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import watchdog
        watchdog.cmd_ignore()
        until = int((tmp_path / ".watchdog-snooze-until").read_text().strip())
        assert until - int(time.time()) >= 24 * 3600 - 100

    def test_unsnooze_removes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".watchdog-snooze-until").write_text("9999999999")
        from lib.kroki_container import watchdog
        watchdog.cmd_unsnooze()
        assert not (tmp_path / ".watchdog-snooze-until").exists()

    def test_stop_invokes_kroki_down(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import watchdog
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            watchdog.cmd_stop()
        assert any("kroki.sh" in " ".join(str(a) for a in c[0][0]) and "down" in str(c[0][0])
                   for c in mock_run.call_args_list)

    def test_status_prints_readable_report(self, tmp_path, monkeypatch, capsys):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".last-use").write_text(str(int(time.time()) - 1800))
        from lib.kroki_container import watchdog
        watchdog.cmd_status()
        out = capsys.readouterr().out
        assert "idle" in out.lower()
        assert "30" in out  # ~30 minutes idle

    def test_snooze_rejects_malformed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import watchdog
        assert watchdog.cmd_snooze("never") != 0


class TestDigestHelpers:
    def test_discover_pod_images_parses_inspect_output(self):
        from lib.kroki_container import version_check
        fake_inspect = json.dumps([{
            "Containers": [
                {"Image": "docker.io/yuzutech/kroki:latest"},
                {"Image": "docker.io/yuzutech/kroki-mermaid:latest"},
                {"Image": "localhost/kroki-gateway-patched:latest"},
            ]
        }])
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_inspect)
            images = version_check.discover_pod_images("kroki")
        assert "docker.io/yuzutech/kroki:latest" in images
        assert "docker.io/yuzutech/kroki-mermaid:latest" in images
        assert "localhost/kroki-gateway-patched:latest" in images

    def test_inspect_local_digest_extracts_sha256(self):
        from lib.kroki_container import version_check
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="sha256:abc123def456\n",
            )
            assert version_check.inspect_local_digest("img:tag") == "sha256:abc123def456"

    def test_inspect_local_digest_missing_returns_none(self):
        from lib.kroki_container import version_check
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
            assert version_check.inspect_local_digest("img:tag") is None

    def test_compute_digest_set_hash_stable(self):
        from lib.kroki_container import version_check
        a = version_check.compute_digest_set_hash({"img1": "sha256:aaa", "img2": "sha256:bbb"})
        b = version_check.compute_digest_set_hash({"img2": "sha256:bbb", "img1": "sha256:aaa"})
        assert a == b  # order-independent
        c = version_check.compute_digest_set_hash({"img1": "sha256:aaa", "img2": "sha256:ccc"})
        assert a != c  # digest-sensitive

    def test_compute_changed_images(self):
        from lib.kroki_container import version_check
        baseline = {"a": "sha256:1", "b": "sha256:2"}
        current = {"a": "sha256:1", "b": "sha256:X"}
        changed = version_check.compute_changed_images(baseline, current)
        assert changed == {"b": ("sha256:2", "sha256:X")}


class TestVersionCheckCycle:
    def _setup(self, tmp_path, monkeypatch, pod_images=None, local_digests=None):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        pod_images = pod_images or ["docker.io/yuzutech/kroki:latest"]
        local_digests = local_digests or {"docker.io/yuzutech/kroki:latest": "sha256:new"}
        self.pod_images = pod_images
        self.local_digests = local_digests

    def test_disabled_is_noop(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / "config.yml").write_text("version_check:\n  enabled: false\n")
        from lib.kroki_container import version_check
        assert version_check.cycle() == 0

    def test_offline_defers_cleanly(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import version_check
        with patch.object(version_check.common, "network_available", return_value=False):
            assert version_check.cycle() == 0

    def test_upgrade_in_progress_defers(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".upgrade-in-progress").write_text(f"{os.getpid()} {int(time.time())}")
        from lib.kroki_container import version_check
        with patch.object(version_check.common, "network_available", return_value=True):
            assert version_check.cycle() == 0

    def test_editor_lock_defers(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import version_check
        with patch.object(version_check.common, "network_available", return_value=True), \
             patch.object(version_check, "read_lock", return_value={"source_path": "x", "started_at": int(time.time())}), \
             patch.object(version_check, "is_stale", return_value=False):
            assert version_check.cycle() == 0

    def test_first_run_pulls_and_writes_baseline_no_notify_if_deferred(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import version_check
        with patch.object(version_check.common, "network_available", return_value=True), \
             patch.object(version_check, "read_lock", return_value=None), \
             patch.object(version_check, "discover_pod_images",
                          return_value=["docker.io/yuzutech/kroki:latest"]), \
             patch.object(version_check, "is_upstream", return_value=True), \
             patch.object(version_check, "pull_image", return_value=True), \
             patch.object(version_check, "inspect_local_digest",
                          return_value="sha256:newcode"), \
             patch.object(version_check.common, "notify_and_log") as mock_notify:
            assert version_check.cycle() == 0
        # baseline written
        baseline = json.loads((tmp_path / ".version-baseline.json").read_text())
        assert baseline == {"docker.io/yuzutech/kroki:latest": "sha256:newcode"}
        # first-run IS a change (baseline was empty) — notify fires
        assert mock_notify.called

    def test_auto_defer_written_after_notify(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import version_check
        with patch.object(version_check.common, "network_available", return_value=True), \
             patch.object(version_check, "read_lock", return_value=None), \
             patch.object(version_check, "discover_pod_images",
                          return_value=["docker.io/yuzutech/kroki:latest"]), \
             patch.object(version_check, "is_upstream", return_value=True), \
             patch.object(version_check, "pull_image", return_value=True), \
             patch.object(version_check, "inspect_local_digest",
                          return_value="sha256:newcode"), \
             patch.object(version_check.common, "notify_and_log"):
            version_check.cycle()
        deferred = json.loads((tmp_path / ".upgrade-deferred.json").read_text())
        now = int(time.time())
        assert deferred["deferred_until"] >= now + 86000
        assert "digest_set_hash" in deferred

    def test_valid_defer_suppresses_notify(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        # Precompute digest_set_hash for the current state
        digest_map = {"docker.io/yuzutech/kroki:latest": "sha256:newcode"}
        from lib.kroki_container import version_check
        dsh = version_check.compute_digest_set_hash(digest_map)
        (tmp_path / ".upgrade-deferred.json").write_text(
            json.dumps({"digest_set_hash": dsh, "deferred_until": int(time.time()) + 3600})
        )
        (tmp_path / ".version-baseline.json").write_text(
            json.dumps({"docker.io/yuzutech/kroki:latest": "sha256:old"})
        )
        with patch.object(version_check.common, "network_available", return_value=True), \
             patch.object(version_check, "read_lock", return_value=None), \
             patch.object(version_check, "discover_pod_images",
                          return_value=["docker.io/yuzutech/kroki:latest"]), \
             patch.object(version_check, "is_upstream", return_value=True), \
             patch.object(version_check, "pull_image", return_value=True), \
             patch.object(version_check, "inspect_local_digest",
                          return_value="sha256:newcode"), \
             patch.object(version_check.common, "notify_and_log") as mock_notify:
            version_check.cycle()
        assert not mock_notify.called

    def test_no_change_is_silent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".version-baseline.json").write_text(
            json.dumps({"docker.io/yuzutech/kroki:latest": "sha256:same"})
        )
        from lib.kroki_container import version_check
        with patch.object(version_check.common, "network_available", return_value=True), \
             patch.object(version_check, "read_lock", return_value=None), \
             patch.object(version_check, "discover_pod_images",
                          return_value=["docker.io/yuzutech/kroki:latest"]), \
             patch.object(version_check, "is_upstream", return_value=True), \
             patch.object(version_check, "pull_image", return_value=True), \
             patch.object(version_check, "inspect_local_digest",
                          return_value="sha256:same"), \
             patch.object(version_check.common, "notify_and_log") as mock_notify:
            version_check.cycle()
        assert not mock_notify.called


class TestVersionCheckSubcommands:
    def test_defer_writes_state(self, tmp_path, monkeypatch):
        import time
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".version-baseline.json").write_text(
            json.dumps({"a:tag": "sha256:x"})
        )
        from lib.kroki_container import version_check
        assert version_check.cmd_defer("7d") == 0
        d = json.loads((tmp_path / ".upgrade-deferred.json").read_text())
        assert d["deferred_until"] - int(time.time()) >= 7 * 86400 - 100

    def test_skip_writes_far_future_defer(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        (tmp_path / ".version-baseline.json").write_text(
            json.dumps({"a:tag": "sha256:x"})
        )
        from lib.kroki_container import version_check
        assert version_check.cmd_skip() == 0
        d = json.loads((tmp_path / ".upgrade-deferred.json").read_text())
        assert d["deferred_until"] >= 4_102_444_800

    def test_status_prints_readable(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_container import version_check
        version_check.cmd_status()
        out = capsys.readouterr().out
        assert "baseline" in out.lower() or "deferred" in out.lower()
