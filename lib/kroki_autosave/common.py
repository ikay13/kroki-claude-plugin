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


def notify_and_log(title: str, body: str) -> None:
    """Fire notify-send (best-effort) and append to notifications.log."""
    # Log first — guarantees audit trail even if notify-send is unavailable
    log_path = state_dir() / "notifications.log"
    try:
        state_dir().mkdir(parents=True, exist_ok=True)
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
