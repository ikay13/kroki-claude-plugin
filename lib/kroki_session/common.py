"""Shared utilities for kroki-session mode-dispatch modules.

Responsibilities:
- Parse/write project memory files (~/.claude/projects/-home-orin/memory/project_<snake>.md)
- Parse/write Obsidian session log files (~/Documents/Obsidian Vault/<Project>/sessions/*.md)
- Git state detection (detached HEAD, merge-in-progress, no-repo, no-git)
- Git diff detection (modified/new/deleted diagram sources)
- Git tag detection with semver filter
- Vault path resolution per obsidian-project-sync.md convention
- Atomic file writes
- Purpose extraction from diagram source first-comment lines
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, TypedDict


class ProjectFolderNotFoundError(Exception):
    """Raised when vault folder for project cannot be resolved."""


class GitState(Enum):
    OK = "ok"
    DETACHED = "detached"
    MERGE = "merge"
    NO_REPO = "no-repo"
    NO_GIT = "no-git"


def vault_paths(project: str, override: Path | None = None) -> Path:
    """Resolve the Obsidian vault folder for a project.

    Convention: ~/Documents/Obsidian Vault/<project>/ (per obsidian-project-sync.md).
    Override: if provided and exists, returned verbatim (bypasses convention).

    Raises:
        ProjectFolderNotFoundError: if override does not exist, or if convention
            path does not exist. Error message names the bypass flag.
    """
    if override is not None:
        if not override.is_dir():
            raise ProjectFolderNotFoundError(
                f"--vault-path override {override} does not exist or is not a directory"
            )
        return override

    home = Path(os.environ.get("HOME", Path.home()))
    path = home / "Documents" / "Obsidian Vault" / project
    if not path.is_dir():
        raise ProjectFolderNotFoundError(
            f"Expected vault folder at {path} (per obsidian-project-sync.md naming rule). "
            f"Not found. Fix: rename the vault folder to match project name '{project}' exactly. "
            f"Bypass for this session: pass --vault-path /path/to/folder"
        )
    return path
