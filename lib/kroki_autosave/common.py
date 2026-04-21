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
