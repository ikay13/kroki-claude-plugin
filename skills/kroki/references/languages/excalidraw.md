# Excalidraw Reference

Excalidraw is a hand-drawn-style whiteboard tool. Kroki accepts the Excalidraw JSON export format and renders it to SVG. Use for sketchy/casual visuals — it is NOT a diagramming DSL.

**Engine:** Companion container (`kroki-excalidraw`)
**File extensions:** `.excalidraw` (JSON)
**Kroki type string:** `excalidraw`

## Minimal example

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [
    {
      "type": "rectangle",
      "version": 1,
      "versionNonce": 1,
      "id": "r1",
      "x": 50, "y": 50, "width": 200, "height": 100,
      "strokeColor": "#000000",
      "backgroundColor": "transparent",
      "fillStyle": "hachure",
      "strokeWidth": 1,
      "strokeStyle": "solid",
      "roughness": 1,
      "opacity": 100,
      "seed": 1, "groupIds": [], "isDeleted": false
    },
    {
      "type": "text",
      "version": 1,
      "versionNonce": 2,
      "id": "t1",
      "x": 100, "y": 90,
      "text": "Hello",
      "fontSize": 20,
      "fontFamily": 1,
      "textAlign": "left",
      "verticalAlign": "top",
      "strokeColor": "#000000",
      "backgroundColor": "transparent",
      "fillStyle": "hachure",
      "strokeWidth": 1,
      "strokeStyle": "solid",
      "roughness": 1,
      "opacity": 100,
      "width": 100, "height": 30,
      "seed": 2, "groupIds": [], "isDeleted": false
    }
  ],
  "appState": {
    "viewBackgroundColor": "#ffffff"
  },
  "files": {}
}
```

## Workflow

Excalidraw JSON is impractical to author by hand. Prefer this workflow:

1. Open https://excalidraw.com (or self-host)
2. Draw the diagram visually
3. **File → Export → Excalidraw (.excalidraw)**
4. Save to your `diagrams/` directory
5. Render with the kroki skill: `render.sh sketch.excalidraw --type excalidraw`

## Legend Support

**Stitch required.** No legend concept — Excalidraw is freeform.

## Common Pitfalls

- Authoring by hand is hard — use the web app and export.
- Required top-level fields: `type`, `version`, `source`, `elements`, `appState`. Missing any of these errors out.
- Each element needs unique `id`. Duplicate IDs collapse silently.
- The `fillStyle: "hachure"` setting is what gives Excalidraw its distinctive look — switching to `"solid"` removes the hand-drawn aesthetic.

## Upstream Docs

- https://excalidraw.com/
- https://github.com/excalidraw/excalidraw/blob/master/dev-docs/docs/codebase/json-schema.mdx (file format)
