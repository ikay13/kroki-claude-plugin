# UMLet Reference

UMLet is a simple UML tool with palette-driven authoring. Kroki accepts the `.uxf` XML export format and renders to SVG. Use when you have existing UMLet files; for new diagrams, PlantUML is usually more compact.

**Engine:** Companion container (`kroki-umlet`)
**File extensions:** `.uxf` (XML)
**Kroki type string:** `umlet`

## Minimal class diagram

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<diagram program="umlet" version="14.3.0">
  <zoom_level>10</zoom_level>
  <element>
    <id>UMLClass</id>
    <coordinates>
      <x>10</x>
      <y>10</y>
      <w>140</w>
      <h>80</h>
    </coordinates>
    <panel_attributes>User
--
+ name : String
+ email : String
--
+ login() : Boolean</panel_attributes>
    <additional_attributes/>
  </element>
  <element>
    <id>UMLClass</id>
    <coordinates>
      <x>200</x>
      <y>10</y>
      <w>140</w>
      <h>80</h>
    </coordinates>
    <panel_attributes>Order
--
+ id : Integer
+ total : Decimal
--
+ submit() : void</panel_attributes>
    <additional_attributes/>
  </element>
  <element>
    <id>Relation</id>
    <coordinates>
      <x>140</x>
      <y>40</y>
      <w>70</w>
      <h>30</h>
    </coordinates>
    <panel_attributes>lt=-
1 *</panel_attributes>
    <additional_attributes>10.0;10.0;60.0;10.0</additional_attributes>
  </element>
</diagram>
```

## Workflow

Author in the UMLet desktop app or umletino.com (web), then export the `.uxf` and render with Kroki for embedding. Hand-writing UXF is rarely worth it.

## Legend Support

**Stitch required.** No native legend.

## Common Pitfalls

- The element type goes in `<id>` — `UMLClass`, `Relation`, `UMLNote`, `UMLActor`, etc. The full list is in the UMLet docs.
- `panel_attributes` is the visible content; `--` separates compartments.
- `additional_attributes` on a `Relation` is a polyline path: `x1;y1;x2;y2;...`.
- Coordinates are absolute — the diagram's bounding box is the union of all element rectangles.
- `lt=-` in a relation is "lifeline / line type"; common values: `-` (solid), `..` (dotted), `<-` (arrow), `<<-` (open arrow).

## Upstream Docs

- https://www.umlet.com/
- https://github.com/umlet/umlet
- https://umletino.com/ (browser version)
