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
    """Atomically create the lock file. Raises LockHeldError if a non-stale lock already exists.

    Behavior on collision:
      1. Attempt O_EXCL create. If succeeds: write payload, return.
      2. On FileExistsError: call read_lock() — this auto-cleans stale or corrupt locks.
         - If read_lock returns None: retry O_EXCL create. Expected to succeed (cleanup ran).
         - If read_lock returns a dict: lock is fresh and valid; raise LockHeldError.
    """
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "source_path": source_path,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    encoded = json.dumps(payload, indent=2) + "\n"

    def _attempt_excl_write() -> bool:
        """Try O_EXCL create. Returns True on success, False on FileExistsError."""
        try:
            fd = os.open(LOCK_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return False
        try:
            os.write(fd, encoded.encode("utf-8"))
        finally:
            os.close(fd)
        return True

    if _attempt_excl_write():
        return payload

    # Collision. Let read_lock do its stale/corrupt cleanup.
    existing = read_lock()
    if existing is not None:
        raise LockHeldError(existing)

    # read_lock cleaned up; retry once.
    if _attempt_excl_write():
        return payload

    # Something else is racing us. Reread to discover what.
    existing = read_lock()
    raise LockHeldError(existing or {"source_path": "<unknown>", "started_at": ""})


def _rename_corrupt_lock(reason: str) -> None:
    """Move the current lock file aside for forensic inspection."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    target = LOCK_PATH.with_name(f"{LOCK_PATH.name}.corrupt.{ts}")
    try:
        os.rename(LOCK_PATH, target)
        print(f"lock.py: corrupt lock moved to {target} ({reason})", file=sys.stderr)
    except FileNotFoundError:
        pass  # Already gone; nothing to rename.


def read_lock() -> Optional[dict]:
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as fp:
            content = fp.read()
    except FileNotFoundError:
        return None

    try:
        lock_dict = json.loads(content)
    except json.JSONDecodeError:
        _rename_corrupt_lock("JSONDecodeError")
        return None

    if not isinstance(lock_dict, dict) or "source_path" not in lock_dict or "started_at" not in lock_dict:
        _rename_corrupt_lock("missing required keys")
        return None

    # Clock-skew check: future started_at is logged but treated as fresh.
    started_at_str = lock_dict["started_at"]
    try:
        started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        _rename_corrupt_lock("unparseable started_at")
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if started_at > now:
        print(
            f"lock.py: warning: started_at is in the future "
            f"(clock skew?); treating as fresh. started_at={started_at_str}",
            file=sys.stderr,
        )
        return lock_dict

    if is_stale(lock_dict):
        age_hours = (now - started_at).total_seconds() / 3600
        try:
            os.unlink(LOCK_PATH)
        except FileNotFoundError:
            pass
        print(f"lock.py: stale lock auto-cleared (age: {age_hours:.1f}h)", file=sys.stderr)
        return None

    return lock_dict


def clear_lock() -> bool:
    try:
        os.unlink(LOCK_PATH)
        return True
    except FileNotFoundError:
        return False


def is_stale(lock_dict: dict) -> bool:
    started_at_str = lock_dict.get("started_at")
    if not started_at_str:
        return True  # Missing key → treat as stale (defensive)
    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age_seconds = (now - started_at).total_seconds()
    return age_seconds >= STALE_THRESHOLD_SECONDS  # Negative age (future) → False


def check_editor_lock(source_path: str) -> LockCheckResult:
    raise NotImplementedError
