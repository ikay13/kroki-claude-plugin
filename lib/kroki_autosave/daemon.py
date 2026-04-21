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


# ============================================================================
# Debounce logic
# ============================================================================

@dataclass
class DebounceEntry:
    timer: threading.Timer
    last_enqueue_ts: float


class Debouncer:
    """Coalesce rapid events per-path within a rolling window.

    Semantics:
      - First enqueue: schedule callback at now + delay.
      - Subsequent enqueue within window: reset timer to new_now + delay.
      - Window expires: fire callback once with the path (callback reads
        latest content itself).

    Implementation: one threading.Timer per path. Cheap; threads die after fire."""

    def __init__(self, delay_seconds: float, on_fire: Callable[[Path], None]):
        self.delay = delay_seconds
        self.on_fire = on_fire
        self._entries: Dict[str, DebounceEntry] = {}
        self._lock = threading.Lock()
        self._stopped = False

    def enqueue(self, path: Path) -> None:
        key = str(path)
        with self._lock:
            if self._stopped:
                return
            entry = self._entries.get(key)
            if entry is not None:
                entry.timer.cancel()
            timer = threading.Timer(self.delay, self._fire, args=(path,))
            timer.daemon = True
            timer.start()
            self._entries[key] = DebounceEntry(
                timer=timer, last_enqueue_ts=time.time(),
            )

    def _fire(self, path: Path) -> None:
        with self._lock:
            self._entries.pop(str(path), None)
        try:
            self.on_fire(path)
        except Exception as e:
            logger.exception("Debouncer: on_fire raised: %s", e)

    def flush(self) -> None:
        """Cancel all pending timers and fire each synchronously."""
        with self._lock:
            paths = [Path(k) for k in self._entries.keys()]
            for entry in self._entries.values():
                entry.timer.cancel()
            self._entries.clear()
        for p in paths:
            try:
                self.on_fire(p)
            except Exception as e:
                logger.exception("Debouncer.flush: on_fire raised: %s", e)

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            for entry in self._entries.values():
                entry.timer.cancel()
            self._entries.clear()
