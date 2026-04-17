---
name: kroki-obsidian
description: Place rendered diagrams into Obsidian vaults — embed dual-theme SVG wikilinks in .md files, maintain diagrams/INDEX.md, and manage the vault symlink. Use when the user says "embed diagram", "add to tracker", "put in session log", "update the index", or when you're writing Obsidian-flavored markdown and a diagram would clarify. Delegates rendering to the `kroki` skill.
---

# kroki-obsidian — Vault Embedding and Indexing

**You should invoke this without asking when you see any of these patterns. No gatekeeping.**

- User says "embed diagram", "add to tracker", "put in session log", "link from README"
- User is editing a markdown file inside an Obsidian vault and a diagram would help
- A prior `kroki` render produced `.light.svg` + `.dark.svg` and needs a home in the vault
- User asks to refresh `diagrams/INDEX.md`

## What This Skill Does

1. **Delegates rendering to `kroki`** — never calls the Kroki server directly
2. **Places files** in the repo's `diagrams/` (reference) or `sessions/` (session) folder
3. **Embeds wikilinks** in a target `.md` file as a dual-theme `<div class="kroki-dual">` block
4. **Maintains `diagrams/INDEX.md`** — auto-regenerated from source + light-SVG pairs
5. **Manages the vault symlink** — `<vault>/<project>/diagrams -> <repo>/diagrams`

All four bash scripts under `scripts/` live at the plugin root:

| Script | Purpose |
|--------|---------|
| `ensure-symlink.sh <repo-dir> <vault-project-dir>` | Create or verify vault diagrams/ symlink |
| `embed-in-md.sh <target.md> <basename> [--section "..."] [--caption "..."]` | Insert dual-wikilink block under a section |
| `update-index.sh <diagrams-dir>` | Regenerate `<diagrams-dir>/INDEX.md` |
| `install-vault-theme.sh <vault-root>` | Install `kroki-theme.css` into `.obsidian/snippets/` |

## How To Embed a Diagram (typical flow)

1. Call the `kroki` skill to render `my-diagram.puml` → produces `my-diagram.light.svg` + `my-diagram.dark.svg`.
2. Ensure the target file is accessible via the vault symlink: `scripts/ensure-symlink.sh ~/my-repo ~/Documents/Obsidian\ Vault/MyProject`.
3. Embed in a markdown file:
   ```bash
   scripts/embed-in-md.sh \
       ~/Documents/Obsidian\ Vault/MyProject/sessions/2026-04-17-MyProject-session-00.md \
       my-diagram \
       --caption "Flow of X through Y"
   ```
4. Regenerate the index:
   ```bash
   scripts/update-index.sh ~/my-repo/diagrams
   ```

Embedding is idempotent — safe to re-run. `update-index.sh` rewrites INDEX.md every time.

## Dual-Render Theme Switching

Plan 2's `render.sh` produces `.light.svg` + `.dark.svg` by default. For Obsidian to show only one variant based on theme, the user must:

1. Run `scripts/install-vault-theme.sh ~/Documents/Obsidian\ Vault` once. This copies `styles/kroki-theme.css` into `<vault>/.obsidian/snippets/kroki-theme.css`.
2. In Obsidian: **Settings → Appearance → CSS snippets → toggle `kroki-theme` on.**

The snippet defines two selectors that hide the opposite-theme SVG inside `<div class="kroki-dual">` wrappers. See [embed-syntax.md](references/embed-syntax.md) for the full block format.

## References

| Topic | Reference file |
|-------|---------------|
| Vault layout, session vs reference, naming | [vault-conventions.md](references/vault-conventions.md) |
| Embed block format, caption, idempotency | [embed-syntax.md](references/embed-syntax.md) |
| INDEX.md structure, purpose extraction | [index-md-template.md](references/index-md-template.md) |
| Naming prefixes (SE/SW/PM) | [../../styles/naming-prefixes.md](../../styles/naming-prefixes.md) |

## Contract

| Field | Detail |
|-------|--------|
| **Inputs** | All `kroki` inputs plus: `project`, `category` (session \| reference), `prefix` (inferred, overridable), `target_md` (optional), `embed_section` (default `## Diagrams`), `caption` (optional) |
| **Outputs** | `render_path` (light + dark), `source_path`, `embedded_in` (list of .md files), `index_updated` (bool), `wikilink` |
| **Side effects** | Writes source + dual renders via `kroki`. Regenerates `INDEX.md`. Ensures vault symlink. Embeds wikilinks idempotently. Creates `## Diagrams` section if absent. |
| **Delegates to** | `kroki` (rendering) |
| **Called by** | User, `kroki-session` (v1: blocked on memory restructuring) |

## Environment

- Repo diagrams dir: `<repo>/diagrams/`
- Vault project dir: `~/Documents/Obsidian Vault/<project>/`
- CSS snippet source: `<plugin>/styles/kroki-theme.css`
- CSS snippet install target: `<vault-root>/.obsidian/snippets/kroki-theme.css`
