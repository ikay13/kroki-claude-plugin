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


def _skip_locked_sources(sources):
    """Filter sources through the editor lock.

    Returns (to_render, skipped) where:
      - to_render: sources not blocked by the lock
      - skipped: stringified source paths that were blocked (source matches lock.source_path)
    """
    from lib.kroki_session.common import check_editor_lock
    to_render = []
    skipped = []
    for src in sources:
        result = check_editor_lock(str(src))
        if result.blocks_target:
            skipped.append(str(src))
            print(
                f"end.py: skipping {src} — editor lock active on this file",
                file=sys.stderr,
            )
        else:
            to_render.append(src)
    return to_render, skipped


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

    # Step 7: per-diagram render loop
    successes: list[dict] = []
    failures: list[dict] = []
    # Step 7a: filter sources through editor lock (Plan 5c).
    sources_to_render, skipped_due_to_editor_lock = _skip_locked_sources(
        list(changes["modified"]) + list(changes["new"])
    )
    for src in sources_to_render:
        try:
            render_result = subprocess.run(
                [str(_SCRIPTS / "render.sh"), str(src), "--mode", "dual"],
                capture_output=True,
                check=False,
            )
            if render_result.returncode != 0:
                failures.append({
                    "src": src,
                    "stage": "render",
                    "error": render_result.stderr.decode(errors="replace").strip()
                              or f"render.sh exit {render_result.returncode}",
                })
                continue
        except FileNotFoundError:
            failures.append({"src": src, "stage": "render", "error": "render.sh not found"})
            continue

        # a11y: advisory
        a11y_flagged = False
        try:
            a11y_result = subprocess.run(
                [str(_SCRIPTS / "a11y-check.sh"), str(src)],
                capture_output=True,
                check=False,
            )
            a11y_flagged = a11y_result.returncode != 0
        except FileNotFoundError:
            failures.append({"src": src, "stage": "a11y-environmental",
                             "error": "a11y-check.sh not found"})
            # Still count as success for render; a11y is advisory
        successes.append({
            "src": src,
            "basename": src.stem,
            "a11y_flagged": a11y_flagged,
        })

    # Step 8: handle deleted
    deleted_names: list[str] = []
    for src in changes["deleted"]:
        deleted_names.append(src.name)

    # Step 9: INDEX regen
    try:
        subprocess.run(
            [str(_SCRIPTS / "update-index.sh"), str(diagrams_dir)],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        failures.append({"src": Path("<index>"), "stage": "index",
                         "error": "update-index.sh not found"})

    # Step 10: session log resolution
    current_log = common.resolve_session_log(project, which="latest")
    embed_skipped = current_log is None
    if embed_skipped:
        print(
            "kroki-session: no session log found at mode=end — embed skipped. "
            "Ensure session-continuity workflow creates the log before kroki-session fires, "
            "then re-invoke.",
            file=sys.stderr,
        )

    # Step 11: embed loop (skipped if no current_log)
    if not embed_skipped:
        for s in list(successes):
            try:
                caption = common.extract_purpose(s["src"])
                subprocess.run(
                    [
                        str(_SCRIPTS / "embed-in-md.sh"),
                        str(current_log),
                        s["basename"],
                        "--section", "## diagrams",
                        "--caption", caption,
                    ],
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                failures.append({
                    "src": s["src"],
                    "stage": "embed",
                    "error": e.stderr.decode(errors="replace").strip() or str(e),
                })
                successes.remove(s)
            except FileNotFoundError:
                failures.append({"src": s["src"], "stage": "embed",
                                 "error": "embed-in-md.sh not found"})
                successes.remove(s)

    # Step 12: milestone handling
    label = milestone_label or auto_milestone_tag
    milestone_result: str = "none"
    if label:
        try:
            subprocess.run(
                [
                    str(_SCRIPTS / "session-snapshot.sh"),
                    "--project", project,
                    "--milestone-label", label,
                    "--vault-path", str(vault_dir),
                ],
                capture_output=True,
                check=True,
            )
            kind = "explicit" if milestone_label else "auto-detect"
            milestone_result = f'"{label}" ({kind}, snapshot generated)'
        except subprocess.CalledProcessError as e:
            failures.append({"src": Path("<milestone>"), "stage": "snapshot",
                             "error": e.stderr.decode(errors="replace").strip() or str(e)})
            kind = "explicit" if milestone_label else "auto-detect"
            milestone_result = f'"{label}" ({kind}, snapshot FAILED)'
        except FileNotFoundError:
            failures.append({"src": Path("<milestone>"), "stage": "snapshot",
                             "error": "session-snapshot.sh not found"})
            milestone_result = f'"{label}" (snapshot SCRIPT MISSING)'

    # Step 13: memory update
    if successes:
        memory = common.parse_memory(project)
        prior = memory.get("touched_diagrams", [])
        new_list = sorted(set(prior + [s["basename"] for s in successes]))
        memory["touched_diagrams"] = new_list
        if "project_name" not in memory:
            memory["project_name"] = project
        common.write_memory(project, memory)

    # Step 14: summary
    total = len(successes) + len(failures)
    rendered_line = f"rendered: {len(successes)}/{max(total, 1)} ({len(failures)} failure(s))"
    print(f"kroki-session(mode=end, project={project}):", file=sys.stderr)
    print(f"  {rendered_line}", file=sys.stderr)
    if skipped_due_to_editor_lock:
        print(
            f"  skipped (editor lock): {len(skipped_due_to_editor_lock)}: "
            f"{', '.join(skipped_due_to_editor_lock)}",
            file=sys.stderr,
        )
    if failures:
        print("  failures:", file=sys.stderr)
        for f in failures:
            print(f"    - {f['src']} (stage: {f['stage']}) — {f['error']}", file=sys.stderr)
    a11y_flagged_names = [s["basename"] for s in successes if s.get("a11y_flagged")]
    if a11y_flagged_names:
        print(
            f"  a11y: {len(a11y_flagged_names)} flagged ({', '.join(a11y_flagged_names)}) "
            f"— advisory, see ~/.kroki-plugin/a11y-reports/",
            file=sys.stderr,
        )
    print(f"  index: diagrams/INDEX.md regenerated", file=sys.stderr)
    if embed_skipped:
        print(f"  embeds: skipped (no session log present)", file=sys.stderr)
    else:
        print(f"  embeds: {len(successes)} added to {current_log.name}#^diagrams",
              file=sys.stderr)
    print(f"  milestone: {milestone_result}", file=sys.stderr)

    # Exit code
    if total == 0:
        exit_code = 0
    elif len(successes) == 0:
        exit_code = 1
    else:
        exit_code = 0
    print(f"  exit: {exit_code}", file=sys.stderr)
    return exit_code


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
