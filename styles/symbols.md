# Symbol Vocabulary

Glyphs used in diagram legends. Drawn from Unicode, renderable in all SVG fonts.

## Flow

| Glyph | Meaning |
|-------|---------|
| → | Directed flow |
| ⇄ | Bidirectional exchange |
| ⇢ | Optional / async flow |

## State

| Glyph | Meaning |
|-------|---------|
| ○ | Start state |
| ● | End state |
| ⊗ | Termination / error |

## Structure

| Glyph | Meaning |
|-------|---------|
| ◆ | Decision / branch |
| ▣ | Subsystem / composite |
| ▢ | Process / activity |
| ☁ | External system / network |
| ⚙ | Service / component |

## Annotation

| Glyph | Meaning |
|-------|---------|
| † | Deprecated / legacy |
| ★ | Critical path / highlight |

## Usage

The legend generator (`render-with-legend.sh`) scans diagram source for each
glyph and includes only those actually present, keeping legends compact.

Canonical YAML: `styles/symbols.yml`.
