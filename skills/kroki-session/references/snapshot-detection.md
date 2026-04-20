# Snapshot Detection — git-diff + activity-gate + semver gate

## Git change detection (mode=end Step 4)

```bash
# Modified (tracked, changed)
git diff --name-only HEAD -- diagrams/

# New (untracked)
git ls-files --others --exclude-standard diagrams/

# Deleted (tracked, removed)
git ls-files --deleted diagrams/
```

Returns `{modified: [...], new: [...], deleted: [...]}` as absolute Path lists.

Deleted files have their render artifacts **preserved** (not auto-deleted). Logged in the summary as "removed this session".

## Activity gate (mode=start)

Skip unless ALL conditions hold:
1. `<vault>/diagrams/` directory exists
2. Either (a) previous session log has entries in `## diagrams` OR (b) memory has entries in `## touched-diagrams`

On skip: `kroki-session: skipped (no diagram activity)` to stderr, exit 0.

## Milestone semver detection (mode=end Step 5)

```bash
git tag --points-at HEAD --list 'v*'
```

Output filtered: only tags matching glob `v*` are candidates. Protects against polluting `diagrams/milestones/` with garbage-tag snapshots (`wip-backup`, `last-good`, etc.).

For each candidate tag:
1. If `diagrams/milestones/<tag>.light.svg` exists → already snapshotted, skip.
2. Else if `diagrams/milestones/<tag>.skip` sentinel exists → user suppressed, skip.
3. Else → this tag is the auto-milestone for this invocation (one per run).

User suppression: `touch diagrams/milestones/<tag>.skip` to permanently suppress a tag.

## Explicit milestone override

User can pass `--milestone-label <label>` to force a milestone with a custom label. Overrides auto-detection. Accepts any label (not limited to semver). `<label>.light.svg` still used as canonical existence marker.
