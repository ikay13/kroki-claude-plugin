"""Editor lock lifecycle for Niolesk sessions.

Provides:
  - write_lock(source_path)   — atomic create; raises LockHeldError on conflict
  - read_lock()               — stale auto-clean, corrupt auto-rename, returns dict or None
  - clear_lock()              — idempotent remove
  - is_stale(lock_dict)       — 2h threshold check
  - check_editor_lock(source) — render-path gate, returns LockCheckResult

Plus a CLI entrypoint (python3 -m lib.kroki_session.lock <open|close|check>)
for bash wrappers to dispatch to.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

LOCK_PATH = Path.home() / ".kroki-plugin" / ".active-editor.lock"
STALE_THRESHOLD_SECONDS = 2 * 60 * 60  # 2 hours


@dataclass
class LockCheckResult:
    locked: bool
    blocks_target: bool
    source_path: Optional[str]
    reason: Literal["ok", "locked-on-target", "locked-other-file", "blank-session"]


class LockHeldError(Exception):
    """Raised by write_lock when a non-stale lock already exists."""

    def __init__(self, held: dict):
        super().__init__(f"editor lock already held for {held.get('source_path')!r}")
        self.held = held


def write_lock(source_path: Optional[str]) -> dict:
    raise NotImplementedError


def read_lock() -> Optional[dict]:
    raise NotImplementedError


def clear_lock() -> bool:
    raise NotImplementedError


def is_stale(lock_dict: dict) -> bool:
    raise NotImplementedError


def check_editor_lock(source_path: str) -> LockCheckResult:
    raise NotImplementedError
