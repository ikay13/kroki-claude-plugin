"""Shared helpers for kroki_container: config, state IO, duration parsing, notify."""

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kroki_container")

DEFAULT_CONFIG = {
    "watchdog": {
        "enabled": True,
        "tier1_hours": 2,
        "tier2_hours": 6,
    },
    "version_check": {
        "enabled": True,
        "cli_path": os.path.expanduser("~/go/bin/kroki"),
    },
    "a11y": {
        "skip_all": False,
    },
}


def state_dir() -> Path:
    """Return ~/.kroki-plugin (or KROKI_STATE_DIR override for tests)."""
    return Path(os.environ.get("KROKI_STATE_DIR", os.path.expanduser("~/.kroki-plugin")))


def _state_path(name: str) -> Path:
    p = state_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p / name


def read_state(name: str) -> Any:
    """Read a state file. Returns parsed JSON for .json files, int for plain numeric
    content, None on any error or missing file."""
    try:
        path = _state_path(name)
        if not path.exists():
            return None
        content = path.read_text().strip()
        if not content:
            return None
        if name.endswith(".json"):
            return json.loads(content)
        # numeric content (e.g., .watchdog-snooze-until)
        try:
            return int(content)
        except ValueError:
            return content
    except Exception as e:
        logger.warning("read_state(%s) failed: %s — treating as missing", name, e)
        return None


def write_state(name: str, value: Any) -> None:
    """Write a state file atomically. JSON-encodes dicts/lists; stringifies scalars."""
    path = _state_path(name)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        if isinstance(value, (dict, list)):
            tmp.write_text(json.dumps(value))
        else:
            tmp.write_text(str(value))
        tmp.replace(path)
    except Exception as e:
        logger.error("write_state(%s) failed: %s", name, e)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def clear_state(name: str) -> None:
    """Delete a state file. No-op if absent."""
    try:
        _state_path(name).unlink(missing_ok=True)
    except Exception as e:
        logger.warning("clear_state(%s) failed: %s", name, e)


_DURATION_RE = re.compile(r"^(\d+)([smhd])$")


def parse_duration(s: str) -> int:
    """Parse '30s', '1m', '2h', '7d' → seconds. Raises ValueError on malformed input."""
    if not s:
        raise ValueError("empty duration")
    m = _DURATION_RE.match(s)
    if not m:
        raise ValueError(f"malformed duration: {s!r} (expected e.g. '1h', '30m', '7d')")
    n, unit = int(m.group(1)), m.group(2)
    factor = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return n * factor


def load_config() -> dict:
    """Load ~/.kroki-plugin/config.yml, merged with defaults. Missing file → defaults."""
    path = state_dir() / "config.yml"
    merged = _deep_copy_defaults()
    if not path.exists():
        return merged
    try:
        # Minimal YAML parser sufficient for our flat schema (no ruamel/pyyaml dep).
        user = _parse_simple_yaml(path.read_text())
        _deep_merge(merged, user)
    except Exception as e:
        logger.warning("config.yml parse failed: %s — using defaults", e)
    return merged


def _deep_copy_defaults() -> dict:
    return json.loads(json.dumps(DEFAULT_CONFIG))


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _parse_simple_yaml(text: str) -> dict:
    """Minimal YAML parser for two-level key/value + indented sub-keys.
    Supports the schema shown in config.yml.example only. Handles 'key: value' and
    'parent:\\n  child: value'. Not a full YAML implementation — sufficient for our
    flat config. Booleans: true/false/yes/no. Integers: \\d+. Strings: rest."""
    result: dict = {}
    current_section: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  "):
            # Child key
            if current_section is None:
                continue
            k, _, v = line.strip().partition(":")
            result.setdefault(current_section, {})[k.strip()] = _coerce(v.strip())
        elif ":" in line:
            k, _, v = line.partition(":")
            v = v.strip()
            if v:
                if v.startswith(":"):
                    raise ValueError(f"malformed YAML value: {raw_line!r}")
                result[k.strip()] = _coerce(v)
                current_section = None
            else:
                current_section = k.strip()
    return result


def _coerce(v: str) -> Any:
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if v.isdigit():
        return int(v)
    # strip surrounding quotes
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v


def network_available(host: str = "hub.docker.io", timeout: int = 5) -> bool:
    """Crude reachability probe via curl -I. False on timeout/DNS/non-2xx. Never raises."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-I", "--max-time", str(timeout),
             f"https://{host}"],
            capture_output=True, timeout=timeout + 2,
        )
        return r.returncode == 0
    except Exception:
        return False


def notify_and_log(
    level: str,
    title: str,
    body: str,
    suggested_cmds: Optional[list] = None,
) -> None:
    """Hybrid notification: log line + notify-send popup. Never raises.

    level: 'info' | 'warning' | 'critical'
    suggested_cmds: list of command strings appended to body as 'Run: <cmd>' lines.
    """
    lines = body.splitlines()
    if suggested_cmds:
        lines.append("")
        for cmd in suggested_cmds:
            lines.append(f"To {_cmd_action_hint(cmd)}: {cmd}")
    full_body = "\n".join(lines)

    _append_notification_log(level, title, full_body, suggested_cmds or [])
    _try_notify_send(level, title, full_body)


def _cmd_action_hint(cmd: str) -> str:
    """Best-effort action verb from command — kroki-watchdog snooze -> 'snooze'."""
    parts = cmd.split()
    if len(parts) >= 2:
        return parts[1]
    return "run"


def _append_notification_log(level: str, title: str, body: str, cmds: list) -> None:
    import time
    log_path = state_dir() / "notifications.log"
    entry = {
        "ts": int(time.time()),
        "level": level,
        "title": title,
        "body": body,
        "suggested_cmds": cmds,
    }
    try:
        with log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        _rotate_log_if_large(log_path, max_lines=500)
    except Exception as e:
        logger.warning("notification log write failed: %s", e)


def _rotate_log_if_large(path: Path, max_lines: int) -> None:
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
        logger.warning("log rotation failed: %s", e)


def _try_notify_send(level: str, title: str, body: str) -> None:
    urgency = {"info": "low", "warning": "normal", "critical": "critical"}.get(level, "normal")
    icon = {"info": "dialog-information", "warning": "dialog-warning",
            "critical": "dialog-error"}.get(level, "dialog-information")
    env = os.environ.copy()
    if "DBUS_SESSION_BUS_ADDRESS" not in env:
        # Systemd user-timer contexts often miss this. Try the standard fallbacks.
        for candidate in (
            os.environ.get("XDG_RUNTIME_DIR", "") + "/bus",
            f"/run/user/{os.getuid()}/bus",
        ):
            if candidate and Path(candidate).exists():
                env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={candidate}"
                break
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-i", icon, title, body],
            env=env, check=False, timeout=5,
            capture_output=True,
        )
    except FileNotFoundError:
        logger.info("notify-send not installed — log-only")
    except Exception as e:
        logger.info("notify-send failed (%s) — log-only", e)
