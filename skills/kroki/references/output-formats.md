# Output Formats

## SVG (default)

- Text-based, scalable, git-friendly
- Embeddable in Obsidian via `![[name.svg]]`
- Editable in any text editor
- Best for: all normal use cases

## PNG

- Raster image, fixed resolution
- Use for: README badges, chat messages, platforms that don't render SVG
- Specify: `render.sh <file> --format png`

## PDF

- Vector-based, print-ready
- Use for: research paper figures, print documents
- Specify: `render.sh <file> --format pdf`
- Note: for research papers, prefer SVG + `flatten.sh` + inkscape/rsvg-convert pipeline
