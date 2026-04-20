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

    # Step 3: pod preflight
    try:
        ph = subprocess.run(
            [str(_SCRIPTS / "pod-health.sh")],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        print("kroki-session: pod-health.sh not found", file=sys.stderr)
        return 2
    if ph.returncode != 0:
        print(
            f"kroki-session: pod preflight failed (rc={ph.returncode}); "
            f"stderr: {ph.stderr.decode(errors='replace').strip()}",
            file=sys.stderr,
        )
        return 2

    diagrams_dir = vault_dir / "diagrams"
    milestones_dir = diagrams_dir / "milestones"

    # Step 3: git state check
    gs = common.git_state_check(cwd=vault_dir)
    if gs == common.GitState.NO_GIT:
        print("kroki-session: git not found in PATH — kroki-session requires git",
              file=sys.stderr)
        return 2
    if gs == common.GitState.DETACHED:
        print("kroki-session: skipped (detached HEAD — session snapshots require a branch)",
              file=sys.stderr)
        return 0
    if gs == common.GitState.MERGE:
        print("kroki-session: skipped (merge in progress — resolve before snapshotting)",
              file=sys.stderr)
        return 0
    if gs == common.GitState.NO_REPO:
        print("kroki-session: skipped (project has no git repo; snapshots skipped)",
              file=sys.stderr)
        return 0

    # Step 4: detect changes
    changes = common.git_detect_changes(diagrams_dir, cwd=vault_dir)

    # Step 5: milestone pre-check
    auto_milestone_tag: str | None = None
    if milestone_label is None:
        tags = common.git_detect_tags_on_head(pattern="v*", cwd=vault_dir)
        for tag in tags:
            light_svg = milestones_dir / f"{tag}.light.svg"
            skip_sentinel = milestones_dir / f"{tag}.skip"
            if not light_svg.exists() and not skip_sentinel.exists():
                auto_milestone_tag = tag
                break

    # Step 6: early exit
    no_changes = not (changes["modified"] or changes["new"] or changes["deleted"])
    if no_changes and milestone_label is None and auto_milestone_tag is None:
        print("kroki-session: skipped (no diagram activity)", file=sys.stderr)
        return 0

    # More steps in next task
    # TODO(task-13): per-diagram render loop + deleted logging
    # TODO(task-14): INDEX regen + session log resolution + embed + milestone + memory + summary

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
