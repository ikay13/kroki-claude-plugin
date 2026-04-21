"""Autosave daemon: inotify event loop, debounce, stage, delete,
divergence.json writer, signals.

Systemd ExecStart target. Runs forever; exits on SIGTERM/SIGINT.
"""

import atexit
import errno
import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from lib.kroki_autosave import common

logger = common.logger


class DaemonAlreadyRunningError(RuntimeError):
    pass


# ============================================================================
# PID file lock
# ============================================================================

class PidFileLock:
    """A simple pidfile-based lock. Detects dead-process stale pidfiles and
    reclaims them."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                existing_pid = int(self.path.read_text().strip())
            except (ValueError, OSError):
                existing_pid = None
            if existing_pid and _process_alive(existing_pid):
                raise DaemonAlreadyRunningError(
                    f"another daemon is running (PID {existing_pid})"
                )
            # Stale — reclaim
            logger.warning("PidFileLock: reclaiming stale pidfile (PID %s)",
                           existing_pid)
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.path.write_text(str(os.getpid()))
        self._acquired = True
        atexit.register(self._cleanup)

    def release(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        if not self._acquired:
            return
        try:
            if self.path.exists():
                current = self.path.read_text().strip()
                if current == str(os.getpid()):
                    self.path.unlink()
        except Exception as e:
            logger.warning("PidFileLock cleanup failed: %s", e)
        self._acquired = False


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we can't signal it
        return True
    except OSError:
        return False
    return True


# ============================================================================
# Daemon runner (minimal — event loop, handlers wired in later tasks)
# ============================================================================

@dataclass
class DaemonState:
    config: Dict
    vault_path: Path
    lock: PidFileLock
    watch_dirs: List[Path] = field(default_factory=list)
    projects: List[str] = field(default_factory=list)
    shutdown_requested: bool = False
    debouncers: Dict[str, "DebounceEntry"] = field(default_factory=dict)
    consecutive_stage_failures: int = 0
    degraded: bool = False
