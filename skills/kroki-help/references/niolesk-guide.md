# Niolesk Guide — In-Browser Kroki Editor

Niolesk is a browser-based source editor with live preview. It runs as a companion container in the kroki pod and is reachable at `http://localhost:8017`.

## When to use Niolesk vs the kroki skill

| Use Niolesk when | Use the kroki skill when |
|------------------|--------------------------|
| Iterating quickly on a single diagram with visual feedback | Generating a diagram from a verbal description |
| Exploring an unfamiliar diagram language | Rendering programmatically (scripts, batch) |
| Demoing kroki to a non-technical user | Embedding into Obsidian or a session log |
| Pasting in source from a colleague to inspect | Persisting source + render to disk |

## Workflow

1. Open `http://localhost:8017` in a browser.
2. Pick a diagram language from the top selector.
3. Edit source in the left pane → preview renders on the right in real time.
4. **To save back to disk:** click the "Download" button. Niolesk does NOT autosave to the host filesystem — browser-internal state is volatile.
5. To share a rendered diagram, click "Share" — Niolesk produces a `localhost:8000/<lang>/svg/<base64>` URL. To get a non-localhost shareable URL, use `~/kroki-claude-plugin/scripts/encode-url.sh` against a public Kroki endpoint (see [kroki4tcl-guide.md](kroki4tcl-guide.md)).

## Editor lock interaction

When the user is actively editing in Niolesk, the plugin should switch to passive mode (no proactive diagram generation, syntax help only). This is signalled by `~/.kroki-plugin/.active-editor.lock`.

| Operation | Effect on plugin behavior |
|-----------|---------------------------|
| `editor-open.sh` writes the lock file | Skill enters passive mode. |
| `editor-close.sh` removes the lock | Skill returns to normal mode. |
| Lock file stale (>2h) | Auto-cleared on next `pod-health.sh` run. |

`editor-open.sh` and `editor-close.sh` are scheduled for Plan 5 (kroki-session). Until then, the lock file is unused.

## Niolesk container

The Niolesk container is part of the kroki pod (started by `~/kroki/kroki.sh up`). To check it specifically:

```bash
podman ps --filter name=niolesk --format '{{.Names}}\t{{.Status}}'
```

If Niolesk is down but the gateway is up, the kroki skill still works — Niolesk failure does NOT block rendering.

## Limitations

- No autosave to host filesystem (browser-internal state only)
- No file-system browser inside the editor — paste source manually
- Limited to languages the gateway supports — see `skills/kroki/references/languages/`
- Live preview blocks the gateway briefly on each render — for batch rendering use the CLI

## Upstream

- https://github.com/niolesk/niolesk
- https://niolesk.top/ (public hosted version)
