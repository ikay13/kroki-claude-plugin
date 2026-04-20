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
