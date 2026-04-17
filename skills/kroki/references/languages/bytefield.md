# bytefield Reference

bytefield (bytefield-svg) is a Clojure-based byte-layout DSL — purpose-built for protocol headers and binary formats. Output is precise byte-accurate visualization.

**Engine:** Companion container (`kroki-bytefield`)
**File extensions:** `.bytefield`
**Kroki type string:** `bytefield`

## Simple header

```bytefield
(defattrs :bg-green {:fill "#a0ffa0"})
(defattrs :bg-blue  {:fill "#a0e0ff"})

(draw-column-headers)
(draw-box "Type"      {:span 2})
(draw-box "Length"    {:span 2 :borders #{:left :top :bottom}})
(draw-box "Value"     {:span 4 :borders #{:right :top :bottom}})
(draw-gap "Payload")
(draw-bottom)
```

## With colors

```bytefield
(defattrs :bg-green {:fill "#a0ffa0"})

(draw-column-headers)
(draw-box "Magic"     {:span 4 :attrs :bg-green})
(draw-box "Version"   {:span 1})
(draw-box "Flags"     {:span 1})
(draw-box "Reserved"  {:span 2})
(draw-box "Payload Length" {:span 4})
(draw-bottom)
```

## Legend Support

**Stitch required.** Use `defattrs` to define color groups, repeat in a separate legend pane.

## Common Pitfalls

- The DSL is Clojure — parens balance matters.
- `:span N` is byte width; row width defaults to 16 bytes (4 columns of 32 bits).
- `(draw-bottom)` is required to close the diagram visually.
- `(draw-gap "label")` inserts a stylized "..." gap for variable-length sections.
- `defattrs` must come before any `draw-*` that uses the attr.

## Upstream Docs

- https://github.com/Deep-Symmetry/bytefield-svg
- https://bytefield-svg.deepsymmetry.org/
