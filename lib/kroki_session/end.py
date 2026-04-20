"""mode=end — session-end bookend with render/embed/index/memory/milestone orchestration."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from lib.kroki_session import common

# Resolved relative to this package's repo root
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS = _PLUGIN_ROOT / "scripts"


def main(
    project: str,
    auto: bool = False,
    milestone_label: str | None = None,
    vault_path_override: Path | None = None,
) -> int:
    """Session-end bookend. Returns exit code 0/1/2 per spec §6.2."""
    # Step 0: env-var gate (only for --auto path)
    if auto and os.environ.get("KROKI_SESSION_AUTO") == "0":
        return 0  # silent

    # Step 2: vault path resolution (Step 1 — pod preflight — comes later when render is needed)
    try:
        vault_dir = common.vault_paths(project, vault_path_override)
    except common.ProjectFolderNotFoundError as e:
        print(f"kroki-session: {e}", file=sys.stderr)
        return 1

    # More steps to be added in subsequent tasks
    # TODO(task-11): pod preflight
    # TODO(task-12): git state + diff detection
    # TODO(task-13): per-diagram render loop
    # TODO(task-14): embed + index + memory + milestone

    return 0


def _cli() -> int:
    parser = argparse.ArgumentParser(description="kroki-session mode=end")
    parser.add_argument("--project", required=True)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--milestone-label", default=None)
    parser.add_argument("--vault-path", type=Path, default=None)
    args = parser.parse_args()
    return main(
        project=args.project,
        auto=args.auto,
        milestone_label=args.milestone_label,
        vault_path_override=args.vault_path,
    )


if __name__ == "__main__":
    sys.exit(_cli())
