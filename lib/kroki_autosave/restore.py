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


# ============================================================================
# CLI handlers
# ============================================================================

def cmd_list(args) -> int:
    cfg = common.load_config()
    vault_path = Path(cfg["autosave"]["vault_path"])
    if args.source_path:
        # Infer project + basename from given path
        try:
            project = common.infer_project_from_path(
                Path(args.source_path), vault_path)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        basename = Path(args.source_path).stem
        rows = list_autosaves(project=project, basename=basename)
        _print_rows(project, rows, group_header=False)
        return 0
    # No arg: list all projects
    root = common.autosaves_root()
    any_printed = False
    for proj_dir in sorted(root.iterdir()) if root.exists() else []:
        if not proj_dir.is_dir():
            continue
        rows = list_autosaves(project=proj_dir.name)
        if rows:
            _print_rows(proj_dir.name, rows, group_header=True)
            any_printed = True
    if not any_printed:
        print("(no autosaves)")
    return 0


def _print_rows(project: str, rows: List[Dict], group_header: bool) -> None:
    if group_header:
        print(f"=== {project} ===")
    # Group by basename
    by_basename: Dict[str, List[Dict]] = {}
    for r in rows:
        by_basename.setdefault(r["basename"] + r["ext"], []).append(r)
    for fname, entries in sorted(by_basename.items()):
        print(f"{fname}:")
        for e in entries:
            print(f"  {e['ts']}  {e['hash']}  "
                  f"{e['lines']} lines  {e['bytes']} bytes  "
                  f"{e['autosave_path']}")


def _infer_project_fallback(source: Path) -> Optional[str]:
    """Walk source parents to find <project>/diagrams or <project>/sessions.
    Returns project name or None."""
    for parent in source.parents:
        if parent.name in ("diagrams", "sessions"):
            project = parent.parent.name
            if project:
                return project
    return None


def cmd_restore(args) -> int:
    cfg = common.load_config()
    vault_path = Path(cfg["autosave"]["vault_path"])
    source = Path(args.source_path).resolve()
    try:
        project = common.infer_project_from_path(source, vault_path)
    except ValueError:
        # Fallback: infer project from path structure without vault constraint
        project = _infer_project_fallback(source)
        if project is None:
            print(
                f"error: cannot infer project from {source} "
                f"(not under vault {vault_path} and no diagrams/sessions parent found)",
                file=sys.stderr,
            )
            return 2
    basename = source.stem
    try:
        row = select_version(project=project, basename=basename, spec=args.spec)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if row is None:
        print(f"error: no autosaves found for {source}", file=sys.stderr)
        return 1
    # Print diff summary
    src_lines = source.read_text(errors="replace").count("\n") if source.exists() else 0
    delta = row["lines"] - src_lines
    delta_str = f"+{delta}" if delta >= 0 else str(delta)
    print(
        f"Restore autosave ({row['ts']}, {row['hash']}) to\n  {source} ?\n"
        f"Diff summary: source has {src_lines} lines; "
        f"autosave has {row['lines']} lines ({delta_str} lines)."
    )
    if not args.yes:
        reply = input("[y/N]: ").strip().lower()
        if reply != "y":
            print("Aborted.")
            return 0
    # Stage current source content as a safety autosave BEFORE overwriting
    if source.exists():
        safety_ts = common.now_utc_iso_compact()
        safety_name = common.build_autosave_filename(basename, safety_ts, source.suffix)
        safety_path = common.project_autosaves_dir(project) / safety_name
        shutil.copy2(source, safety_path)
        print(f"Pre-restore content staged as {safety_name}.")
    # Atomic restore
    tmp = source.with_suffix(source.suffix + ".tmp")
    shutil.copy2(row["autosave_path"], tmp)
    tmp.replace(source)
    print("Restored.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kroki-autosave")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list autosaves")
    p_list.add_argument("source_path", nargs="?", default=None)
    p_list.set_defaults(func=cmd_list)

    p_restore = sub.add_parser("restore", help="restore an autosave over a source file")
    p_restore.add_argument("source_path")
    p_restore.add_argument("spec", nargs="?", default=None,
                           help="timestamp (YYYYMMDDTHHMMSSZ) or hash prefix")
    p_restore.add_argument("--yes", action="store_true",
                           help="non-interactive; skip confirmation")
    p_restore.set_defaults(func=cmd_restore)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
