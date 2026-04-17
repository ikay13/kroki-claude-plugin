# Vault Conventions

This reference codifies how `kroki-obsidian` places diagrams in an Obsidian vault and how it names them. Mirrors §6 and §8 of the design spec.

## Two diagram categories

| Category | Folder | Versioning | Examples |
|----------|--------|-----------|----------|
| **Reference** (living project artifacts) | `diagrams/` | Overwrites current — git preserves history for rollback | Architecture, data flow, components, dependencies, ERD, HLD/LLD |
| **Session** (narrative artifacts) | `sessions/` | Accumulates — each session yields distinct files, never overwritten | Bug flow, before/after, troubleshooting trace, decision walkthrough |

A project can have both folders; `kroki-obsidian` routes based on the `category` input (`session` or `reference`).

## Vault layout per project

```
~/Documents/Obsidian Vault/<project>/
├── <project> Project.md         # tracker
├── diagrams/                    # symlink -> ~/<repo>/diagrams/
│   ├── INDEX.md                 # auto-generated
│   ├── arch-<project>-<topic>.puml
│   ├── arch-<project>-<topic>.light.svg
│   └── arch-<project>-<topic>.dark.svg
└── sessions/
    ├── YYYY-MM-DD-<project>-session-NN.md
    ├── YYYY-MM-DD-<project>-bug-<topic>.puml
    ├── YYYY-MM-DD-<project>-bug-<topic>.light.svg
    └── YYYY-MM-DD-<project>-bug-<topic>.dark.svg
```

`diagrams/` is a symlink. Obsidian treats symlinked folders identically to real folders. The symlink is created by `scripts/ensure-symlink.sh`.

## Naming convention

**Reference diagrams** (live under `diagrams/`):

```
<prefix>-<project-slug>-<topic>.<ext>
```

Example: `arch-msp-layer-stack.puml`

**Session diagrams** (live under `sessions/`):

```
YYYY-MM-DD-<project>-<prefix>-<topic>.<ext>
```

Example: `2026-04-17-MSP-bug-adapter-routing.puml`

`<prefix>` is one of the SE/SW/PM-aligned prefixes in `styles/naming-prefixes.md`. Adding a new prefix = one row in that table; no code change.

## Collision resolution

- **Reference:** new render overwrites prior file. Git preserves history. For intentional parallel variants, suffix `-opt-a`, `-opt-b`.
- **Session:** intra-session duplicates suffix `-v2`, `-v3`.

## Symlink safety

`ensure-symlink.sh` is strictly additive:

- If the vault's `diagrams/` is already a symlink pointing to the repo's `diagrams/` → exit 0 (no change).
- If the target path exists as a regular directory or file → exit 1 (user resolves manually). The script will **not** overwrite existing content.
- If the vault path itself doesn't exist → exit 3 (usage error).

Rationale: losing a folder of hand-authored Obsidian notes to a misplaced symlink is not recoverable. Fail loud, never silently clobber.

## Why symlink and not copy

- **Single source of truth:** diagrams live in the repo; Obsidian is the viewer.
- **Git-native:** renders commit alongside code changes; vault picks up instantly.
- **No sync daemons:** nothing to schedule, nothing to go stale.
