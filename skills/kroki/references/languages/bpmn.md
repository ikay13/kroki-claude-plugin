# BPMN Reference

BPMN (Business Process Model and Notation) is the OMG standard for business-process diagrams. Kroki uses bpmn-js — input is BPMN 2.0 XML (a hand-written sample is verbose, so most users export from a modeler like Camunda Modeler, then render via Kroki for embedding).

**Engine:** Companion container (`kroki-bpmn`)
**File extensions:** `.bpmn` (XML)
**Kroki type string:** `bpmn`

## Minimal valid BPMN process

```xml
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  id="defs"
                  targetNamespace="http://example.com/bpmn">
  <bpmn:process id="proc" isExecutable="false">
    <bpmn:startEvent id="start" name="Start"/>
    <bpmn:task id="task1" name="Do Work"/>
    <bpmn:endEvent id="end" name="Done"/>
    <bpmn:sequenceFlow id="f1" sourceRef="start" targetRef="task1"/>
    <bpmn:sequenceFlow id="f2" sourceRef="task1" targetRef="end"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="diag">
    <bpmndi:BPMNPlane id="plane" bpmnElement="proc">
      <bpmndi:BPMNShape id="start_di" bpmnElement="start">
        <dc:Bounds x="100" y="100" width="36" height="36"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="task1_di" bpmnElement="task1">
        <dc:Bounds x="200" y="80" width="100" height="80"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="end_di" bpmnElement="end">
        <dc:Bounds x="350" y="100" width="36" height="36"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="f1_di" bpmnElement="f1">
        <di:waypoint x="136" y="118"/>
        <di:waypoint x="200" y="120"/>
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="f2_di" bpmnElement="f2">
        <di:waypoint x="300" y="120"/>
        <di:waypoint x="350" y="118"/>
      </bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
```

## Legend Support

**Stitch required.** Native BPMN legend symbols are part of the notation itself (event/task/gateway icons) — no separate legend macro.

## Common Pitfalls

- BPMN 2.0 requires BOTH a `<bpmn:process>` AND a `<bpmndi:BPMNDiagram>` — process-only XML renders as an empty box.
- Every shape needs `<dc:Bounds>` (x/y/width/height) — bpmn-js does not auto-layout.
- Hand-writing BPMN XML is tedious. Prefer Camunda Modeler / bpmn.io to author, then Kroki to render. Save the .bpmn output and render it via the kroki skill.
- IDs must be unique across the document.

## Upstream Docs

- https://github.com/bpmn-io/bpmn-js
- https://www.omg.org/spec/BPMN/2.0.2/PDF
