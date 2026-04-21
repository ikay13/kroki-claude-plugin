"""mode=start — read-only diagram inventory surface at session start."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from lib.kroki_session import common


def _state_dir_for_autosaves() -> Path:
    """Resolve ~/.kroki-plugin honoring KROKI_STATE_DIR for tests."""
    return Path(os.environ.get("KROKI_STATE_DIR",
                               os.path.expanduser("~/.kroki-plugin")))


def _parse_iso(s: str):
    """Tolerant ISO-8601 parser (handles 'Z' suffix)."""
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s[:-1]).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s)
    except (ValueError, AttributeError):
        return None


def scan_divergence(project: str,
                    freshness_window_seconds: int = 600) -> List[Dict]:
    """Read ~/.kroki-plugin/autosaves/divergence.json; filter rows for this
    project. Returns [] if file absent, bad, or the daemon's last cycle
    checked_at is older than freshness_window_seconds."""
    path = _state_dir_for_autosaves() / "autosaves" / "divergence.json"
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(rows, list):
        return []

    # Freshness gate
    now = datetime.now(timezone.utc)
    parsed_timestamps = [
        _parse_iso(r.get("checked_at")) for r in rows
        if isinstance(r, dict) and r.get("checked_at")
    ]
    parsed_timestamps = [t for t in parsed_timestamps if t is not None]
    if not parsed_timestamps:
        return []
    newest = max(parsed_timestamps)
    if (now - newest).total_seconds() > freshness_window_seconds:
        return []

    out: List[Dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("project") != project:
            continue
        sp = r.get("source_path")
        if not sp:
            continue
        out.append({
            "source_path": sp,
            "last_autosave_ts": r.get("last_autosave_ts", ""),
            "status": r.get("status", "unknown"),
            "hint": f"kroki-autosave list {sp}",
        })
    return out


def main(project: str, auto: bool = False, vault_path_override: Path | None = None) -> int:
    """Session-start bookend. Read-only. Exit 0 always.

    Activity gate:
        1. <project>/diagrams/ exists, AND
        2. Previous session log has ## diagrams entries OR memory touched_diagrams non-empty.
    If gate fails → silent skip with one-line stderr note.

    Env-var gate:
        If auto=True AND KROKI_SESSION_AUTO=0 → exit silent (no stderr).
        Explicit invocations (auto=False) ignore the env var.
    """
    if auto and os.environ.get("KROKI_SESSION_AUTO") == "0":
        return 0  # silent auto-suppression

    try:
        vault_dir = common.vault_paths(project, vault_path_override)
    except common.ProjectFolderNotFoundError as e:
        print(f"kroki-session: {e}", file=sys.stderr)
        return 0

    diagrams_dir = vault_dir / "diagrams"
    if not diagrams_dir.is_dir():
        print(f"kroki-session: skipped (no diagrams/ directory in {vault_dir})", file=sys.stderr)
        return 0

    memory = common.parse_memory(project)
    touched_mem = memory.get("touched_diagrams", [])

    prev_log_path = common.resolve_session_log(project, which="previous")
    prev_diagrams: list[str] = []
    if prev_log_path is not None:
        prev_diagrams = common.parse_session_log(prev_log_path).get("diagrams", [])

    if not touched_mem and not prev_diagrams:
        print("kroki-session: skipped (no diagram activity)", file=sys.stderr)
        return 0

    index_path = diagrams_dir / "INDEX.md"
    reference_summary = common.parse_index_summary(index_path) if index_path.exists() else []

    # Combine prior signals into loaded_diagrams (deduped, preserving order)
    loaded: list[str] = []
    seen = set()
    for d in prev_diagrams + touched_mem:
        if d not in seen:
            loaded.append(d)
            seen.add(d)

    payload = {
        "mode": "start",
        "project": project,
        "vault_dir": str(vault_dir),
        "loaded_diagrams": loaded,
        "reference_summary": reference_summary,
        "last_next_steps": memory.get("next_steps", []),
    }
    # Plan 5d: surface autosave divergence in start-mode payload
    payload["autosave_divergence"] = scan_divergence(project)

    print(json.dumps(payload, indent=2))
    print(
        f"kroki-session: surfaced {len(loaded)} prior diagrams + {len(reference_summary)} references",
        file=sys.stderr,
    )
    return 0


def _cli() -> int:
    parser = argparse.ArgumentParser(description="kroki-session mode=start")
    parser.add_argument("--project", required=True)
    parser.add_argument("--auto", action="store_true",
                        help="Mark as INSTALLER-driven auto-invoke; gates KROKI_SESSION_AUTO env var")
    parser.add_argument("--vault-path", type=Path, default=None)
    args = parser.parse_args()
    return main(project=args.project, auto=args.auto, vault_path_override=args.vault_path)


if __name__ == "__main__":
    sys.exit(_cli())
