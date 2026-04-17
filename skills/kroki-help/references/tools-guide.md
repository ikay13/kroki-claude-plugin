# Tools Guide — Kroki Ecosystem on This Host

Inventory of every kroki-related tool installed on this Jetson Orin. Use this as the source of truth before recommending a workflow.

## Servers

| Tool | Path / URL | Purpose |
|------|-----------|---------|
| Kroki gateway | `http://localhost:8000` | Main HTTP API. POST source → SVG/PNG/PDF. |
| Niolesk editor | `http://localhost:8017` | Browser-based source editor + live preview. |
| Patched gateway image | `~/kroki/Dockerfile.kroki-patched` | Built locally — fixes symbolator engine. |

## CLI tools

| Tool | Path | Purpose |
|------|------|---------|
| Kroki CLI (Go) | `~/go/bin/kroki` | Command-line render. See [cli-cheatsheet.md](cli-cheatsheet.md). |
| `kroki.sh` | `~/kroki/kroki.sh` | Pod lifecycle: `up`, `down`, `status`, `logs`. See [pod-management.md](pod-management.md). |
| Plugin `render.sh` | `~/kroki-claude-plugin/scripts/render.sh` | Plugin entry point: pod-health + render. |
| Plugin `pod-health.sh` | `~/kroki-claude-plugin/scripts/pod-health.sh` | Health check + auto-start + circuit breaker. |
| Plugin `encode-url.sh` | `~/kroki-claude-plugin/scripts/encode-url.sh` | Text → kroki URL. See [kroki4tcl-guide.md](kroki4tcl-guide.md). |
| Plugin `decode-url.sh` | `~/kroki-claude-plugin/scripts/decode-url.sh` | Kroki URL → text. |
| Plugin `extract-chunks.sh` | `~/kroki-claude-plugin/scripts/extract-chunks.sh` | Pull fenced diagram blocks from .md. |
| `kroki4tcl` (Tcl 8.6) | `~/kroki4tcl/kroki4tcl/kroki4tcl.tcl` | Reference Tcl implementation (needs Tcl 8.6 patch — use the bash wrappers above instead). |

## Container infrastructure

| Tool | Path | Purpose |
|------|------|---------|
| Podman | system | Rootless OCI runtime — used by `kroki.sh`. |
| Pod compose | `~/kroki.yml` | Multi-container pod spec: gateway, mermaid, bpmn, etc. Endpoint: `localhost:8000`, timeout: 30s. |

## Plugin state directory

| Path | Purpose |
|------|---------|
| `~/.kroki-plugin/` | All plugin runtime state. Created by `pod-health.sh`. |
| `~/.kroki-plugin/.last-use` | Unix timestamp of most recent render. Used by container-watchdog. |
| `~/.kroki-plugin/.pod-circuit-open` | Circuit-breaker flag. Present → rendering disabled this session. |
| `~/.kroki-plugin/.pod-restart-count` | Recent failed restart count. Resets on success or after 10 minutes. |

## How they fit together

```
User
  │
  ├─ asks Claude → kroki skill → render.sh ──► pod-health.sh ──► kroki.sh up (if needed)
  │                                  │                              │
  │                                  └─ ~/go/bin/kroki ──HTTP──► localhost:8000 (pod)
  │
  └─ wants to share diagram → encode-url.sh ──► localhost:8000/<lang>/svg/<base64>
                                                                    │
                              decode-url.sh ◄──URL─────────────────┘
```

## Upstream

- Kroki project: https://kroki.io/
- Kroki gateway repo: https://github.com/yuzutech/kroki
- Niolesk: https://niolesk.top/
- kroki4tcl: https://github.com/mittelmark/kroki4tcl
