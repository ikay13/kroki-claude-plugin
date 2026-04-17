"""Tests for kroki-obsidian bash scripts (Plan 3).

Each script is invoked via subprocess in an isolated ``tmp_path`` so tests
never touch the user's real vault or repo. All fixtures are inline.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
STYLES = REPO_ROOT / "styles"


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess:
    cmd = [str(SCRIPTS / script_name), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


class TestEnsureSymlink:
    def test_creates_symlink_when_target_missing(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "diagrams").mkdir(parents=True)
        vault_project = tmp_path / "vault" / "MyProject"
        vault_project.mkdir(parents=True)

        result = run_script("ensure-symlink.sh", str(repo), str(vault_project))

        assert result.returncode == 0, result.stderr
        target = vault_project / "diagrams"
        assert target.is_symlink()
        assert target.resolve() == (repo / "diagrams").resolve()

    def test_idempotent_when_symlink_already_correct(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "diagrams").mkdir(parents=True)
        vault_project = tmp_path / "vault" / "MyProject"
        vault_project.mkdir(parents=True)
        (vault_project / "diagrams").symlink_to(repo / "diagrams")

        result = run_script("ensure-symlink.sh", str(repo), str(vault_project))

        assert result.returncode == 0, result.stderr
        assert (vault_project / "diagrams").is_symlink()

    def test_errors_when_symlink_points_to_wrong_target(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "diagrams").mkdir(parents=True)
        other = tmp_path / "other"
        (other / "diagrams").mkdir(parents=True)
        vault_project = tmp_path / "vault" / "MyProject"
        vault_project.mkdir(parents=True)
        (vault_project / "diagrams").symlink_to(other / "diagrams")

        result = run_script("ensure-symlink.sh", str(repo), str(vault_project))

        assert result.returncode == 1
        assert "wrong target" in result.stderr

    def test_errors_when_target_exists_as_real_dir(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "diagrams").mkdir(parents=True)
        vault_project = tmp_path / "vault" / "MyProject"
        (vault_project / "diagrams").mkdir(parents=True)

        result = run_script("ensure-symlink.sh", str(repo), str(vault_project))

        assert result.returncode == 1
        assert "not a symlink" in result.stderr

    def test_usage_error_on_missing_args(self, tmp_path: Path) -> None:
        result = run_script("ensure-symlink.sh")
        assert result.returncode == 3
