# Embed Syntax

This reference documents exactly what `scripts/embed-in-md.sh` inserts into a markdown file, and why. Mirrors §8 of the design spec.

## The embed block

Every diagram is embedded as a `<div class="kroki-dual">` wrapper containing **both** theme variants:

```markdown
<div class="kroki-dual">
![[<basename>.light.svg]]
![[<basename>.dark.svg]]
</div>
*Figure -- <caption>*
```

- `<basename>` is the diagram stem without extension (e.g., `arch-msp-overview`).
- The trailing caption line is omitted when no caption is supplied.

The wrapper div is required so the theme-switching CSS in `styles/kroki-theme.css` can hide the opposite-theme variant. Without the wrapper, both images would render stacked.

## Why wikilinks, not Markdown image links

Obsidian's wikilink syntax (`![[file.svg]]`) resolves by filename alone — no path required. This means a diagram in the repo's `diagrams/` dir can be embedded in any markdown file across the vault without knowing the relative path. Markdown image syntax (`![](../diagrams/file.svg)`) breaks when the markdown moves.

## Section insertion

Default section heading: `## Diagrams`. Override via `--section "## Other Heading"`.

- **Section exists in target file:** block is inserted immediately after the section heading line (blank lines around it).
- **Section absent:** the section heading is appended at end-of-file, then the block.

## Idempotency

Before writing anything, `embed-in-md.sh` greps for `[[<basename>.light.svg]]` in the target file. If found → exit 0, no change. This makes repeated invocations safe (e.g., re-running a session-end workflow).

## Caption format

```
*Figure -- <caption text>*
```

The `--` is a double hyphen (em-dash substitute) to visually separate "Figure" from the caption. Italic wrapping is Markdown-rendered; Obsidian displays it as italic grey text below the image.

## Interaction with the CSS snippet

The CSS snippet installed by `scripts/install-vault-theme.sh` is:

```css
.theme-light .kroki-dual img[src$=".dark.svg"]  { display: none; }
.theme-dark  .kroki-dual img[src$=".light.svg"] { display: none; }
```

- In **light theme**: the `.dark.svg` variant is hidden inside `.kroki-dual` wrappers.
- In **dark theme**: the `.light.svg` variant is hidden.
- Outside `.kroki-dual`: both variants display (useful for side-by-side comparison in analysis docs).

## Example: session log embed

Given a session log at `~/Documents/Obsidian Vault/MSP/sessions/2026-04-17-MSP-session-03.md` and a rendered diagram pair at `diagrams/bug-adapter-routing.{light,dark}.svg`, calling:

```bash
scripts/embed-in-md.sh \
    ~/Documents/Obsidian\ Vault/MSP/sessions/2026-04-17-MSP-session-03.md \
    bug-adapter-routing \
    --caption "Adapter routing failure path"
```

...inserts (under `## Diagrams`, creating the section if absent):

```markdown
## Diagrams

<div class="kroki-dual">
![[bug-adapter-routing.light.svg]]
![[bug-adapter-routing.dark.svg]]
</div>
*Figure -- Adapter routing failure path*
```
