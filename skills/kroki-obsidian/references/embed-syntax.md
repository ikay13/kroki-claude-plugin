# Embed Syntax

This reference documents exactly what `scripts/embed-in-md.sh` inserts into a markdown file, and why. Mirrors §8 of the design spec.

## The embed block

Every diagram is embedded as a `<div class="kroki-dual">` wrapper containing **both** theme variants, with blank lines inside the div:

```markdown
<div class="kroki-dual">

![[<basename>.light.svg]]
![[<basename>.dark.svg]]

</div>
*Figure -- <caption>*
```

- `<basename>` is the diagram stem without extension (e.g., `arch-msp-overview`).
- The trailing caption line is omitted when no caption is supplied.
- **Blank lines inside the div are required.** Obsidian follows CommonMark's HTML-block rule — without blank lines, `<div>...</div>` is parsed as raw HTML and the `![[...]]` wikilinks render as literal text instead of embedded images.

The wrapper div provides semantic grouping. The actual theme switching is performed by the CSS snippet in `styles/kroki-theme.css`, which uses global attribute selectors (`[src$=".dark.svg"]`, `[alt$=".dark.svg"]`) rather than scoping to `.kroki-dual` — Obsidian's renderer strips custom classes from user-authored divs, so scoped rules don't match the rendered DOM.

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
.theme-light [src$=".dark.svg"],
.theme-light [alt$=".dark.svg"]  { display: none !important; }
.theme-dark  [src$=".light.svg"],
.theme-dark  [alt$=".light.svg"] { display: none !important; }
```

- In **light theme**: any SVG whose `src` or `alt` ends in `.dark.svg` is hidden.
- In **dark theme**: any SVG whose `src` or `alt` ends in `.light.svg` is hidden.
- Rules are global (vault-wide), not scoped to `.kroki-dual` — Obsidian strips the custom class at render time, so scoped rules never match. Attribute selectors are used instead of `img[...]` because Obsidian wraps wikilink embeds in a `<span class="internal-embed" src="..." alt="...">` rather than an `<img>` tag.
- Side effect: if you embed `.light.svg`/`.dark.svg` pairs **outside** kroki diagrams and want both variants visible, comment out the snippet's global rules. The `.kroki-dual` wrapper remains in the markup as semantic grouping but has no CSS effect in default Obsidian.

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
