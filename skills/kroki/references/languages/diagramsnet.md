# diagrams.net Reference

diagrams.net (formerly draw.io) is a visual diagramming tool. Kroki accepts the drawio XML format and renders to SVG/PNG. Use to embed diagrams that were authored in drawio without re-creating them in another DSL.

**Engine:** Companion container (`kroki-diagramsnet`)
**File extensions:** `.drawio`, `.xml` (drawio XML)
**Kroki type string:** `diagramsnet`

## Minimal drawio XML

```xml
<mxfile>
  <diagram name="Page-1">
    <mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="2" value="Hello" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="3" value="World" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#d5e8d4;" vertex="1" parent="1">
          <mxGeometry x="240" y="40" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="4" style="endArrow=classic;html=1;" edge="1" parent="1" source="2" target="3">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

## Workflow

Authoring drawio XML by hand is impractical. Use this flow:

1. Open https://app.diagrams.net (or the desktop app)
2. Draw the diagram
3. **File → Export as → XML** (uncompressed)
4. Save the `.drawio` or `.xml` file to your `diagrams/` directory
5. Render with: `render.sh file.drawio --type diagramsnet`

## Legend Support

**Native** (legend lives in the drawio canvas — author it visually as part of the diagram). No separate legend macro.

## Common Pitfalls

- The drawio editor compresses XML by default. **Uncheck "Compressed" before saving** for Kroki to accept it. Compressed (`.drawio` with binary blob) will not render.
- Multi-page documents: Kroki renders only the first `<diagram>`. To render a specific page, export that page individually.
- Mathematical formulas in cell labels (`html=1` style) are rendered as plain text, not formatted.
- Custom shape libraries (loaded as plugins in the editor) often fail to render in Kroki — stick to the built-in shape set for portability.

## Upstream Docs

- https://www.diagrams.net/
- https://www.drawio.com/blog/format
