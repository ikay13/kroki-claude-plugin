"""Shared helpers for kroki_autosave: config, state IO, path utils,
pure functions for file filtering, divergence classification, prune TTL.
"""

import hashlib
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kroki_autosave")

DEFAULT_CONFIG = {
    "autosave": {
        "enabled": True,
        "vault_path": os.path.expanduser("~/Documents/Obsidian Vault"),
        "ttl_days": 7,
        "debounce_seconds": 2,
        "rescan_interval_hours": 1,
        "session_start_scan": True,
        "divergence_stale_threshold_seconds": 60,
        "divergence_freshness_window_seconds": 600,
        "notify_on_delete": True,
    }
}


def state_dir() -> Path:
    """Return ~/.kroki-plugin (or KROKI_STATE_DIR override for tests)."""
    return Path(os.environ.get("KROKI_STATE_DIR", os.path.expanduser("~/.kroki-plugin")))


def autosaves_root() -> Path:
    """Return the autosaves subdirectory (creates with mode 700 if absent)."""
    root = state_dir() / "autosaves"
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    # Defensive chmod every call — cheap, ensures security invariant
    os.chmod(root, 0o700)
    return root


def project_autosaves_dir(project: str) -> Path:
    """Return the per-project autosaves subdir; creates if absent."""
    d = autosaves_root() / project
    d.mkdir(parents=True, exist_ok=True)
    return d


def atomic_write(path: Path, content: str) -> None:
    """Write atomically: write to <path>.tmp, then rename. 3-line pattern
    duplicated per design spec §3.4 to avoid cross-package import."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content)
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _parse_simple_yaml(text: str) -> Dict:
    """Parse a limited YAML subset: top-level keys mapped to dicts of key:value.
    Matches 5b's _parse_simple_yaml contract. Raises ValueError on malformed input."""
    result: Dict[str, Any] = {}
    current_section: Optional[str] = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            # top-level section
            if ":" not in line:
                raise ValueError(f"line {lineno}: expected 'section:' got {line!r}")
            key, _, rest = line.partition(":")
            key = key.strip()
            rest_stripped = rest.split("#")[0].strip()
            # Reject degenerate forms like "autosave: : broken:"
            if rest_stripped.startswith(":"):
                raise ValueError(f"line {lineno}: malformed top-level key: {line!r}")
            if rest_stripped and not rest.strip().startswith("#"):
                # inline scalar top-level key (rare; not used by 5d)
                result[key] = _coerce_scalar(rest_stripped)
                current_section = None
            else:
                result[key] = {}
                current_section = key
        else:
            # nested key under current section
            if current_section is None:
                raise ValueError(f"line {lineno}: indent without section: {line!r}")
            stripped = line.strip()
            # Reject degenerate forms like "key: : value"
            if stripped.count(":") > 0 and stripped.split(":", 1)[1].lstrip().startswith(":"):
                raise ValueError(f"line {lineno}: malformed key: {line!r}")
            if ":" not in stripped:
                raise ValueError(f"line {lineno}: expected 'key: value' got {line!r}")
            k, _, v = stripped.partition(":")
            comment_stripped = v.split("#")[0].strip()
            result[current_section][k.strip()] = _coerce_scalar(comment_stripped)
    return result


def _coerce_scalar(s: str) -> Any:
    """Coerce a YAML-ish scalar string to bool/int/str. Tilde-expand strings
    that look like paths."""
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    # String — strip quotes if present; tilde-expand if starts with ~
    s = s.strip().strip('"').strip("'")
    if s.startswith("~"):
        s = os.path.expanduser(s)
    return s


def _deep_merge_defaults(user: Dict, defaults: Dict) -> Dict:
    """Recursively fill missing keys from defaults."""
    result = dict(user)
    for k, v in defaults.items():
        if k not in result:
            result[k] = v
        elif isinstance(v, dict) and isinstance(result[k], dict):
            result[k] = _deep_merge_defaults(result[k], v)
    return result


def load_config() -> Dict:
    """Load config.yml from state_dir; fill missing keys with DEFAULT_CONFIG.
    Never raises — on parse failure, logs WARN and returns DEFAULT_CONFIG."""
    cfg_path = state_dir() / "config.yml"
    if not cfg_path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    try:
        parsed = _parse_simple_yaml(cfg_path.read_text())
    except ValueError as e:
        logger.warning("load_config: bad config.yml (%s) — using defaults", e)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    return _deep_merge_defaults(parsed, DEFAULT_CONFIG)


def infer_project_from_path(source_path: Path, vault_path: Path) -> str:
    """Given a source file path and the vault root, return the project name
    (directory between vault_path and source_path). Raises ValueError if
    source_path is not inside vault_path/<project>/{diagrams,sessions}/."""
    source_path = Path(source_path).resolve()
    vault_path = Path(vault_path).resolve()
    try:
        rel = source_path.relative_to(vault_path)
    except ValueError as e:
        raise ValueError(f"path {source_path} not under vault {vault_path}") from e
    parts = rel.parts
    if len(parts) < 3 or parts[1] not in ("diagrams", "sessions"):
        raise ValueError(
            f"path {source_path} not under <vault>/<project>/{{diagrams,sessions}}/"
        )
    return parts[0]


def discover_projects(vault_path: Path) -> Tuple[List[str], List[Path]]:
    """Glob <vault_path>/*/diagrams/ and */sessions/; return (projects, watch_dirs).
    Skips projects with a `.no-autosave` marker file at their root. Returns
    ([], []) if vault_path doesn't exist."""
    vault_path = Path(vault_path)
    if not vault_path.is_dir():
        return [], []
    projects_set = set()
    watch_dirs: List[Path] = []
    for project_dir in sorted(vault_path.iterdir()):
        if not project_dir.is_dir():
            continue
        if (project_dir / ".no-autosave").exists():
            logger.info("discover_projects: skipping %s (.no-autosave)", project_dir.name)
            continue
        has_any = False
        for sub in ("diagrams", "sessions"):
            d = project_dir / sub
            if d.is_dir():
                watch_dirs.append(d)
                has_any = True
        if has_any:
            projects_set.add(project_dir.name)
    return sorted(projects_set), watch_dirs


def _rotate_log_if_large(path: Path, max_lines: int = 500) -> None:
    """Rotate log to <path>.1 if it exceeds max_lines. Duplicated per §3.4."""
    try:
        if not path.exists():
            return
        with path.open() as f:
            lines = f.readlines()
        if len(lines) <= max_lines:
            return
        archive = path.with_suffix(path.suffix + ".1")
        archive.write_text("".join(lines[:-max_lines]))
        path.write_text("".join(lines[-max_lines:]))
    except Exception as e:
        logger.debug("_rotate_log_if_large: %s", e)


def notify_and_log(title: str, body: str) -> None:
    """Fire notify-send (best-effort) and append to notifications.log."""
    # Log first — guarantees audit trail even if notify-send is unavailable
    log_path = state_dir() / "notifications.log"
    try:
        state_dir().mkdir(parents=True, exist_ok=True)
        _rotate_log_if_large(log_path, max_lines=500)
        with log_path.open("a") as fh:
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            fh.write(f"{ts} kroki-autosave {title} — {body}\n")
    except Exception as e:
        logger.warning("notify_and_log: log write failed: %s", e)

    try:
        subprocess.run(
            ["notify-send", title, body],
            check=False, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.info("notify_and_log: notify-send unavailable (%s) — logged only", e)
    except Exception as e:
        logger.warning("notify_and_log: notify-send failed: %s", e)


# ============================================================================
# Filename roundtrip
# ============================================================================

_AUTOSAVE_RE = re.compile(r"^(?P<basename>.+)\.(?P<ts>\d{8}T\d{6}Z)(?P<ext>\.[^.]+)$")


def build_autosave_filename(basename: str, ts: str, ext: str) -> str:
    """basename + '.' + ts + ext (e.g., 'arch-foo' + '20260421T130815Z' + '.puml')."""
    if not ext.startswith("."):
        ext = "." + ext
    return f"{basename}.{ts}{ext}"


def parse_autosave_filename(fname: str) -> Tuple[str, str, str]:
    """Inverse of build_autosave_filename. Raises ValueError on non-match."""
    m = _AUTOSAVE_RE.match(fname)
    if not m:
        raise ValueError(f"not an autosave filename: {fname!r}")
    return m["basename"], m["ts"], m["ext"]


def now_utc_iso_compact() -> str:
    """Return YYYYMMDDTHHMMSSZ for use in autosave filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ============================================================================
# File filter (deny-list per design §2.6)
# ============================================================================

_DENY_EXT_SUFFIXES = (".light.svg", ".dark.svg", ".tmp.svg", ".tmp.png")


def should_skip(path: Path) -> bool:
    """Return True if the file should NOT be staged (filtered out)."""
    p = Path(path)
    name = p.name
    if name.startswith("."):
        return True
    if name == "INDEX.md":
        return True
    for suffix in _DENY_EXT_SUFFIXES:
        if name.endswith(suffix):
            return True
    if ".kroki-autosave" in p.parts:
        return True
    return False


# ============================================================================
# Divergence classification (pure function per design §5.8)
# ============================================================================

class Status(Enum):
    MATCHES = "matches"
    DIVERGED = "diverged"
    IN_FLIGHT = "in_flight"
    SOURCE_MISSING = "source_missing"
    NO_HISTORY = "no_history"


def classify(source_exists: bool, source_hash: Optional[str],
             autosave_exists: bool, autosave_hash: Optional[str],
             autosave_age_seconds: Optional[float],
             stale_threshold_seconds: int) -> Status:
    if not source_exists and autosave_exists:
        return Status.SOURCE_MISSING
    if not autosave_exists:
        return Status.NO_HISTORY
    if source_hash == autosave_hash:
        return Status.MATCHES
    if autosave_age_seconds is not None and autosave_age_seconds < stale_threshold_seconds:
        return Status.IN_FLIGHT
    return Status.DIVERGED


def hash_file(path: Path, prefix_chars: int = 12) -> str:
    """Return truncated SHA-256 hex (default 12 chars). Raises on read error."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:prefix_chars]


# ============================================================================
# Prune TTL + Trash-move (per no-rm-use-trash.md rule)
# ============================================================================

def _trash_dir() -> Path:
    """System Trash (XDG). Overrideable via KROKI_TRASH_DIR env var for tests."""
    override = os.environ.get("KROKI_TRASH_DIR")
    if override:
        p = Path(override)
    else:
        p = Path(os.path.expanduser("~/.local/share/Trash/files"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_prunable(project_dir: Path, ttl_days: int, now_ts: float) -> List[Path]:
    """Return list of autosave files in project_dir older than ttl_days (strict >)."""
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return []
    cutoff = now_ts - ttl_days * 86400
    prunable: List[Path] = []
    for entry in project_dir.iterdir():
        if not entry.is_file():
            continue
        try:
            _, _, _ = parse_autosave_filename(entry.name)
        except ValueError:
            continue
        if entry.stat().st_mtime < cutoff:
            prunable.append(entry)
    return prunable


def move_to_trash(path: Path) -> Optional[Path]:
    """Move a file to the system Trash per no-rm-use-trash.md. Returns the
    destination path, or None on failure."""
    path = Path(path)
    if not path.exists():
        return None
    trash = _trash_dir()
    dest = trash / path.name
    if dest.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = trash / f"{path.name}.autosave-trash-{ts}"
    try:
        path.rename(dest)
        return dest
    except Exception as e:
        logger.warning("move_to_trash(%s) failed: %s", path, e)
        return None
