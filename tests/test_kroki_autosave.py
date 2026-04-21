"""Unit tests for lib/kroki_autosave/*."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
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


class TestFilenameRoundtrip:
    @pytest.mark.parametrize("basename,ts,ext", [
        ("arch-msp", "20260421T130815Z", ".puml"),
        ("2026-04-21-Kroki-Plugin-session-10", "20260421T132201Z", ".md"),
        ("seq-flow", "20260421T131042Z", ".mmd"),
        ("diagram.with.dots", "20260421T131042Z", ".d2"),
    ])
    def test_roundtrip(self, basename, ts, ext):
        from lib.kroki_autosave import common
        fname = common.build_autosave_filename(basename, ts, ext)
        assert fname == f"{basename}.{ts}{ext}"
        parsed_basename, parsed_ts, parsed_ext = common.parse_autosave_filename(fname)
        assert parsed_basename == basename
        assert parsed_ts == ts
        assert parsed_ext == ext


class TestFileFilter:
    @pytest.mark.parametrize("fname,should_skip", [
        ("arch-foo.puml", False),
        ("flow.mmd", False),
        ("2026-04-21-session-00.md", False),
        ("INDEX.md", True),
        ("arch-foo.light.svg", True),
        ("arch-foo.dark.svg", True),
        ("render.tmp.svg", True),
        ("output.tmp.png", True),
        (".hidden", True),
        (".DS_Store", True),
    ])
    def test_filter(self, fname, should_skip):
        from lib.kroki_autosave import common
        assert common.should_skip(Path(fname)) == should_skip

    def test_skip_under_kroki_autosave_dir(self, tmp_path):
        from lib.kroki_autosave import common
        path = tmp_path / ".kroki-autosave" / "old.puml"
        path.parent.mkdir()
        path.write_text("a")
        assert common.should_skip(path) is True


class TestClassifyDivergence:
    def test_matches(self):
        from lib.kroki_autosave import common
        s = common.classify(
            source_exists=True, source_hash="abc",
            autosave_exists=True, autosave_hash="abc",
            autosave_age_seconds=3600, stale_threshold_seconds=60,
        )
        assert s == common.Status.MATCHES

    def test_diverged(self):
        from lib.kroki_autosave import common
        s = common.classify(
            source_exists=True, source_hash="abc",
            autosave_exists=True, autosave_hash="def",
            autosave_age_seconds=3600, stale_threshold_seconds=60,
        )
        assert s == common.Status.DIVERGED

    def test_in_flight(self):
        from lib.kroki_autosave import common
        s = common.classify(
            source_exists=True, source_hash="abc",
            autosave_exists=True, autosave_hash="def",
            autosave_age_seconds=30, stale_threshold_seconds=60,
        )
        assert s == common.Status.IN_FLIGHT

    def test_source_missing(self):
        from lib.kroki_autosave import common
        s = common.classify(
            source_exists=False, source_hash=None,
            autosave_exists=True, autosave_hash="abc",
            autosave_age_seconds=3600, stale_threshold_seconds=60,
        )
        assert s == common.Status.SOURCE_MISSING

    def test_no_history_new_file(self):
        from lib.kroki_autosave import common
        s = common.classify(
            source_exists=True, source_hash="abc",
            autosave_exists=False, autosave_hash=None,
            autosave_age_seconds=None, stale_threshold_seconds=60,
        )
        assert s == common.Status.NO_HISTORY

    def test_boundary_at_threshold(self):
        """Age exactly at threshold: strict < means age==threshold → DIVERGED."""
        from lib.kroki_autosave import common
        s = common.classify(
            source_exists=True, source_hash="a",
            autosave_exists=True, autosave_hash="b",
            autosave_age_seconds=60, stale_threshold_seconds=60,
        )
        assert s == common.Status.DIVERGED


class TestPruneTTL:
    def test_just_fresh_kept(self, tmp_path):
        from lib.kroki_autosave import common
        f = tmp_path / "a.20260420T000000Z.puml"
        f.write_text("x")
        now = datetime.now(timezone.utc).timestamp()
        os.utime(f, (now - 6 * 86400, now - 6 * 86400))
        to_prune = common.find_prunable(tmp_path, ttl_days=7, now_ts=now)
        assert to_prune == []

    def test_just_expired_pruned(self, tmp_path):
        from lib.kroki_autosave import common
        f = tmp_path / "a.20260414T000000Z.puml"
        f.write_text("x")
        now = datetime.now(timezone.utc).timestamp()
        os.utime(f, (now - 8 * 86400, now - 8 * 86400))
        to_prune = common.find_prunable(tmp_path, ttl_days=7, now_ts=now)
        assert f in to_prune

    def test_boundary_at_exactly_ttl(self, tmp_path):
        from lib.kroki_autosave import common
        f = tmp_path / "a.20260414T000000Z.puml"
        f.write_text("x")
        now = datetime.now(timezone.utc).timestamp()
        # Exactly 7 days old — strict > comparison means NOT pruned at exactly ttl
        os.utime(f, (now - 7 * 86400, now - 7 * 86400))
        to_prune = common.find_prunable(tmp_path, ttl_days=7, now_ts=now)
        assert to_prune == []

    def test_empty_dir(self, tmp_path):
        from lib.kroki_autosave import common
        now = datetime.now(timezone.utc).timestamp()
        assert common.find_prunable(tmp_path, ttl_days=7, now_ts=now) == []

    def test_move_to_trash_preserves_content(self, tmp_path, monkeypatch):
        from lib.kroki_autosave import common
        trash = tmp_path / "trash"
        trash.mkdir()
        monkeypatch.setattr(common, "_trash_dir", lambda: trash)
        f = tmp_path / "victim.puml"
        f.write_text("ORIGINAL")
        result = common.move_to_trash(f)
        assert result is not None
        assert result.exists()
        assert result.read_text() == "ORIGINAL"
        assert not f.exists()

    def test_trash_collision_appends_timestamp(self, tmp_path, monkeypatch):
        from lib.kroki_autosave import common
        trash = tmp_path / "trash"
        trash.mkdir()
        monkeypatch.setattr(common, "_trash_dir", lambda: trash)
        f1 = tmp_path / "victim.puml"
        f1.write_text("1")
        r1 = common.move_to_trash(f1)
        f2 = tmp_path / "victim.puml"
        f2.write_text("2")
        r2 = common.move_to_trash(f2)
        assert r1 != r2
        assert r2.name.startswith("victim.puml.autosave-trash-")


class TestRestoreSelection:
    def test_list_empty_project(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import restore
        rows = restore.list_autosaves(project="Kroki-Plugin")
        assert rows == []

    def test_list_single_entry(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        (proj / "arch.20260421T130815Z.puml").write_text("content")
        from lib.kroki_autosave import restore
        rows = restore.list_autosaves(project="Kroki-Plugin")
        assert len(rows) == 1
        assert rows[0]["basename"] == "arch"
        assert rows[0]["ts"] == "20260421T130815Z"
        assert rows[0]["ext"] == ".puml"
        assert rows[0]["bytes"] == len("content")
        assert rows[0]["lines"] == 1
        assert len(rows[0]["hash"]) == 12

    def test_list_sorted_descending(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        (proj / "arch.20260421T120000Z.puml").write_text("a")
        (proj / "arch.20260421T130000Z.puml").write_text("b")
        (proj / "arch.20260421T140000Z.puml").write_text("c")
        from lib.kroki_autosave import restore
        rows = restore.list_autosaves(project="Kroki-Plugin", basename="arch")
        timestamps = [r["ts"] for r in rows]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_filter_by_basename(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        (proj / "foo.20260421T120000Z.puml").write_text("x")
        (proj / "bar.20260421T120000Z.puml").write_text("y")
        from lib.kroki_autosave import restore
        rows_all = restore.list_autosaves(project="Kroki-Plugin")
        rows_foo = restore.list_autosaves(project="Kroki-Plugin", basename="foo")
        assert len(rows_all) == 2
        assert len(rows_foo) == 1
        assert rows_foo[0]["basename"] == "foo"

    def test_select_most_recent_no_spec(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        (proj / "foo.20260421T120000Z.puml").write_text("old")
        (proj / "foo.20260421T130000Z.puml").write_text("new")
        from lib.kroki_autosave import restore
        row = restore.select_version(project="Kroki-Plugin", basename="foo")
        assert row["ts"] == "20260421T130000Z"

    def test_select_by_timestamp_exact(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        (proj / "foo.20260421T120000Z.puml").write_text("a")
        (proj / "foo.20260421T130000Z.puml").write_text("b")
        from lib.kroki_autosave import restore
        row = restore.select_version(
            project="Kroki-Plugin", basename="foo",
            spec="20260421T120000Z",
        )
        assert row["ts"] == "20260421T120000Z"

    def test_select_by_hash_prefix_unique(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        (proj / "foo.20260421T120000Z.puml").write_text("alpha")
        (proj / "foo.20260421T130000Z.puml").write_text("beta")
        from lib.kroki_autosave import restore
        rows = restore.list_autosaves(project="Kroki-Plugin")
        some_hash = rows[0]["hash"][:6]
        row = restore.select_version(
            project="Kroki-Plugin", basename="foo",
            spec=some_hash,
        )
        assert row["hash"].startswith(some_hash)

    def test_select_by_hash_prefix_ambiguous_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        # Two files with the SAME content → identical hash
        (proj / "foo.20260421T120000Z.puml").write_text("alpha")
        (proj / "foo.20260421T130000Z.puml").write_text("alpha")
        from lib.kroki_autosave import restore
        rows = restore.list_autosaves(project="Kroki-Plugin")
        shared_hash = rows[0]["hash"][:6]
        with pytest.raises(ValueError, match="ambiguous"):
            restore.select_version(
                project="Kroki-Plugin", basename="foo",
                spec=shared_hash,
            )


class TestRestoreCLI:
    def test_list_subcommand_no_args(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("PYTHONPATH", str(Path.cwd()))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        (proj / "arch.20260421T120000Z.puml").write_text("alpha")
        result = subprocess.run(
            [sys.executable, "-m", "lib.kroki_autosave.restore", "list"],
            capture_output=True, text=True,
            env={**os.environ, "KROKI_STATE_DIR": str(tmp_path)},
        )
        assert result.returncode == 0
        assert "Kroki-Plugin" in result.stdout
        assert "arch" in result.stdout
        assert "20260421T120000Z" in result.stdout

    def test_restore_subcommand_atomic_replace(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        vault = tmp_path / "Vault"
        proj_src = vault / "Kroki-Plugin" / "diagrams"
        proj_src.mkdir(parents=True)
        source = proj_src / "arch.puml"
        source.write_text("CURRENT")
        # Stage an "older" version to recover
        proj_stage = tmp_path / "autosaves" / "Kroki-Plugin"
        proj_stage.mkdir(parents=True)
        stage_file = proj_stage / "arch.20260421T120000Z.puml"
        stage_file.write_text("ORIGINAL")
        # Restore with --yes (non-interactive)
        result = subprocess.run(
            [sys.executable, "-m", "lib.kroki_autosave.restore",
             "restore", str(source), "--yes"],
            capture_output=True, text=True,
            env={**os.environ, "KROKI_STATE_DIR": str(tmp_path)},
        )
        assert result.returncode == 0
        assert source.read_text() == "ORIGINAL"
        # Pre-restore content should have been staged as an autosave
        staged = list(proj_stage.glob("arch.*.puml"))
        assert len(staged) >= 2  # original + pre-restore

    def test_restore_subcommand_missing_source(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        result = subprocess.run(
            [sys.executable, "-m", "lib.kroki_autosave.restore",
             "restore", "/nonexistent/foo.puml", "--yes"],
            capture_output=True, text=True,
            env={**os.environ, "KROKI_STATE_DIR": str(tmp_path)},
        )
        assert result.returncode != 0  # error exit


class TestPruneCLI:
    def test_prune_dry_run_lists_without_deleting(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        old = proj / "foo.20260410T000000Z.puml"
        old.write_text("a")
        now = datetime.now(timezone.utc).timestamp()
        os.utime(old, (now - 30 * 86400, now - 30 * 86400))  # 30 days old

        result = subprocess.run(
            [sys.executable, "-m", "lib.kroki_autosave.restore",
             "prune", "--dry-run"],
            capture_output=True, text=True,
            env={**os.environ, "KROKI_STATE_DIR": str(tmp_path)},
        )
        assert result.returncode == 0
        assert "foo.20260410T000000Z.puml" in result.stdout
        assert old.exists()  # NOT deleted in dry-run

    def test_prune_real_moves_to_trash(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        trash = tmp_path / "Trash"
        trash.mkdir()
        monkeypatch.setenv("KROKI_TRASH_DIR", str(trash))
        proj = tmp_path / "autosaves" / "Kroki-Plugin"
        proj.mkdir(parents=True)
        old = proj / "foo.20260410T000000Z.puml"
        old.write_text("a")
        now = datetime.now(timezone.utc).timestamp()
        os.utime(old, (now - 30 * 86400, now - 30 * 86400))

        result = subprocess.run(
            [sys.executable, "-m", "lib.kroki_autosave.restore", "prune"],
            capture_output=True, text=True,
            env={
                **os.environ,
                "KROKI_STATE_DIR": str(tmp_path),
                "KROKI_TRASH_DIR": str(trash),
            },
        )
        assert result.returncode == 0
        assert not old.exists()
        assert len(list(trash.iterdir())) == 1

class TestStatusCLI:
    def test_status_no_daemon(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        result = subprocess.run(
            [sys.executable, "-m", "lib.kroki_autosave.restore", "status"],
            capture_output=True, text=True,
            env={**os.environ, "KROKI_STATE_DIR": str(tmp_path)},
        )
        # Exits 0 even with no daemon; reports "inactive" or similar
        assert result.returncode == 0
        assert "kroki-autosave.service" in result.stdout


class TestPidfileLock:
    def test_acquire_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import daemon
        lock = daemon.PidFileLock(tmp_path / "autosaves" / ".autosave-daemon.pid")
        lock.acquire()
        assert lock.path.exists()
        assert int(lock.path.read_text().strip()) == os.getpid()
        lock.release()

    def test_release_removes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import daemon
        lock = daemon.PidFileLock(tmp_path / "autosaves" / ".autosave-daemon.pid")
        lock.acquire()
        lock.release()
        assert not lock.path.exists()

    def test_double_acquire_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import daemon
        (tmp_path / "autosaves").mkdir(parents=True)
        lockA = daemon.PidFileLock(tmp_path / "autosaves" / ".autosave-daemon.pid")
        lockB = daemon.PidFileLock(tmp_path / "autosaves" / ".autosave-daemon.pid")
        lockA.acquire()
        try:
            with pytest.raises(daemon.DaemonAlreadyRunningError):
                lockB.acquire()
        finally:
            lockA.release()

    def test_dead_process_reclaim(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KROKI_STATE_DIR", str(tmp_path))
        from lib.kroki_autosave import daemon
        (tmp_path / "autosaves").mkdir(parents=True)
        pidfile = tmp_path / "autosaves" / ".autosave-daemon.pid"
        # Simulate stale: write a PID that doesn't exist
        # (PID 99999999 is almost certainly not running)
        pidfile.write_text("99999999")
        lock = daemon.PidFileLock(pidfile)
        lock.acquire()  # should reclaim
        assert int(pidfile.read_text().strip()) == os.getpid()
        lock.release()
