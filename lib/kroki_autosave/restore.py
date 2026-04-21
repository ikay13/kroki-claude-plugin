"""Autosave restore CLI: list, restore, prune, status, reload subcommands.

The core selection logic is pure-function and unit-testable;
CLI subcommand handlers live at the bottom.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from lib.kroki_autosave import common

logger = common.logger


# ============================================================================
# Pure-function selection logic
# ============================================================================

def list_autosaves(project: str, basename: Optional[str] = None) -> List[Dict]:
    """List all autosaves for a project, optionally filtered by basename.
    Returns rows sorted newest-first. Each row:
      {basename, ts, ext, hash, lines, bytes, autosave_path}
    """
    proj_dir = common.autosaves_root() / project
    if not proj_dir.is_dir():
        return []
    rows: List[Dict] = []
    for entry in proj_dir.iterdir():
        if not entry.is_file():
            continue
        try:
            b, ts, ext = common.parse_autosave_filename(entry.name)
        except ValueError:
            continue
        if basename is not None and b != basename:
            continue
        size = entry.stat().st_size
        try:
            text = entry.read_text(errors="replace")
            lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        except Exception:
            lines = 0
        rows.append({
            "basename": b,
            "ts": ts,
            "ext": ext,
            "hash": common.hash_file(entry),
            "lines": lines,
            "bytes": size,
            "autosave_path": str(entry),
        })
    rows.sort(key=lambda r: r["ts"], reverse=True)
    return rows


def select_version(project: str, basename: str, spec: Optional[str] = None) -> Optional[Dict]:
    """Pick one row from list_autosaves. spec can be:
      - None → most recent
      - An ISO timestamp (YYYYMMDDTHHMMSSZ) → exact match
      - A hash prefix (<12 chars) → prefix match (raises ValueError if ambiguous)
    Returns the row dict, or None if no match."""
    rows = list_autosaves(project=project, basename=basename)
    if not rows:
        return None
    if spec is None:
        return rows[0]
    # Exact timestamp match
    for r in rows:
        if r["ts"] == spec:
            return r
    # Hash prefix match
    matches = [r for r in rows if r["hash"].startswith(spec)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"ambiguous spec {spec!r}: matches {len(matches)} autosaves")
    return None
