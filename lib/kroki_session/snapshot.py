"""Milestone composite snapshot: dual-theme multi-panel SVG for a labeled release moment."""
from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys
from pathlib import Path

from lib.kroki_session import common
from lib import kroki_util

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS = _PLUGIN_ROOT / "scripts"

# Recognized diagram source extensions (align with render.sh extension-alias map)
_SRC_EXTS = {".puml", ".plantuml", ".mmd", ".mermaid", ".dot", ".gv",
             ".graphviz", ".d2", ".c4", ".c4plantuml", ".svg.source"}


def _collect_sources(diagrams_dir: Path) -> list[Path]:
    """Return all diagram source files directly in diagrams_dir (not subdirs)."""
    if not diagrams_dir.is_dir():
        return []
    out = []
    for p in sorted(diagrams_dir.iterdir()):
        if p.is_file() and p.suffix in _SRC_EXTS:
            out.append(p)
    return out


def main(
    project: str,
    milestone_label: str,
    vault_path_override: Path | None = None,
) -> int:
    """Generate a milestone composite. All-or-nothing: exit 1 on any failure."""
    try:
        vault_dir = common.vault_paths(project, vault_path_override)
    except common.ProjectFolderNotFoundError as e:
        print(f"kroki-session(snapshot): {e}", file=sys.stderr)
        return 1

    diagrams_dir = vault_dir / "diagrams"
    milestones_dir = diagrams_dir / "milestones"
    milestones_dir.mkdir(parents=True, exist_ok=True)

    sources = _collect_sources(diagrams_dir)
    if not sources:
        print(f"kroki-session(snapshot): no diagram sources in {diagrams_dir}", file=sys.stderr)
        return 1

    # Render each source dual-theme
    light_svgs: list[Path] = []
    dark_svgs: list[Path] = []
    for src in sources:
        try:
            r = subprocess.run(
                [str(_SCRIPTS / "render.sh"), str(src), "--mode", "dual"],
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            print("kroki-session(snapshot): render.sh not found", file=sys.stderr)
            return 1
        if r.returncode != 0:
            print(
                f"kroki-session(snapshot): render failed for {src.name}: "
                f"{r.stderr.decode(errors='replace').strip()}",
                file=sys.stderr,
            )
            return 1
        light = src.with_suffix(".light.svg")
        dark = src.with_suffix(".dark.svg")
        if not light.exists() or not dark.exists():
            print(f"kroki-session(snapshot): render produced no output for {src.name}",
                  file=sys.stderr)
            return 1
        light_svgs.append(light)
        dark_svgs.append(dark)

    # Stitch composites
    try:
        light_composite_bytes = kroki_util.stitch_svgs_vertical(
            [s.read_text() for s in light_svgs]
        )
        dark_composite_bytes = kroki_util.stitch_svgs_vertical(
            [s.read_text() for s in dark_svgs]
        )
    except Exception as e:  # noqa: BLE001 — stitching errors should abort
        print(f"kroki-session(snapshot): stitch failed — {e}", file=sys.stderr)
        return 1

    # Atomic writes
    light_out = milestones_dir / f"{milestone_label}.light.svg"
    dark_out = milestones_dir / f"{milestone_label}.dark.svg"
    sources_out = milestones_dir / f"{milestone_label}.source-list.txt"

    light_out.write_text(light_composite_bytes)
    dark_out.write_text(dark_composite_bytes)
    sources_out.write_text("\n".join(s.name for s in sources) + "\n")

    # Update milestones/INDEX.md (lightweight)
    _update_milestones_index(milestones_dir, milestone_label, len(sources))

    print(
        f"kroki-session(snapshot): milestone {milestone_label} generated "
        f"({len(sources)} sources composited)",
        file=sys.stderr,
    )
    return 0


def _update_milestones_index(milestones_dir: Path, label: str, source_count: int) -> None:
    """Append/update a row in milestones/INDEX.md. Idempotent on label."""
    index_path = milestones_dir / "INDEX.md"
    today = _dt.date.today().isoformat()

    header = "# Milestones\n\n| Label | Date | Sources | Snapshot |\n|---|---|---|---|\n"
    new_row = f"| {label} | {today} | {source_count} | [[{label}.light.svg\\|{label}]] |\n"

    if not index_path.exists():
        content = header + new_row
    else:
        existing = index_path.read_text()
        # If this label already has a row, replace it; else append
        lines = existing.split("\n")
        replaced = False
        for i, line in enumerate(lines):
            if line.startswith(f"| {label} |"):
                lines[i] = new_row.rstrip("\n")
                replaced = True
                break
        if replaced:
            content = "\n".join(lines)
        else:
            if not existing.endswith("\n"):
                existing += "\n"
            content = existing + new_row

    common.atomic_write(index_path, content)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="kroki-session milestone snapshot")
    parser.add_argument("--project", required=True)
    parser.add_argument("--milestone-label", required=True)
    parser.add_argument("--vault-path", type=Path, default=None)
    args = parser.parse_args()
    return main(
        project=args.project,
        milestone_label=args.milestone_label,
        vault_path_override=args.vault_path,
    )


if __name__ == "__main__":
    sys.exit(_cli())
