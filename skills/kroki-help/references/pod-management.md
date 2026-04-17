# Pod Management

The Kroki gateway runs as a podman pod. The plugin auto-starts it on first render via `pod-health.sh`. This document explains the lifecycle and how to recover from common failures.

## Lifecycle commands

All commands wrap `~/kroki/kroki.sh`:

```bash
~/kroki/kroki.sh up        # Start the pod (idempotent — no-op if already running)
~/kroki/kroki.sh down      # Stop and remove the pod
~/kroki/kroki.sh status    # Show pod and container statuses
~/kroki/kroki.sh logs      # Follow gateway logs (Ctrl+C to detach)
```

## Auto-start

`~/kroki-claude-plugin/scripts/pod-health.sh` runs before every render (called by `render.sh`). It:

1. Touches `~/.kroki-plugin/.last-use` (used by the watchdog for idle detection)
2. Checks the circuit-breaker flag — if open and within the 10-minute window, exits 1
3. GETs `http://localhost:8000` with 5s timeout
4. If unhealthy: increments restart counter, runs `kroki.sh up` (or `down && up` if running but unhealthy), polls health every 2s for up to 30s
5. After 2 failed restart attempts in 10 minutes: opens circuit breaker, writes flag, exits 1

## Circuit breaker

When `~/.kroki-plugin/.pod-circuit-open` exists and was written within the last 10 minutes, all renders fail fast.

To force a retry (use sparingly — usually means the pod is genuinely broken and needs investigation):

```bash
mv ~/.kroki-plugin/.pod-circuit-open ~/.local/share/Trash/files/pod-circuit-open_$(date +%Y%m%d_%H%M%S)
~/kroki-claude-plugin/scripts/pod-health.sh
```

## OOM detection

If a container is killed by the OOM killer (exit code 137), `pod-health.sh` surfaces a specific diagnostic:

```
OOM DETECTED: Container was killed due to memory pressure.
Free RAM: <amount>
Consider stopping unused containers.
```

Mitigations:

- Stop other heavy containers (`podman ps`)
- Increase `~/kroki.yml` memory limits (gateway default is 512Mi — bump to 1Gi for large diagrams)
- For TikZ/Vega/VegaLite: reduce diagram complexity or render in batches

## Watchdog (planned, Plan 5)

`scripts/container-watchdog.sh` will run as a systemd user timer every 15 minutes:

| Tier | Idle age | Action |
|------|----------|--------|
| 1 | >1h | `notify-send` + log; user can ignore/snooze/stop |
| 2 | >2h, no response | Auto-stop; log action |

Idle is measured against `~/.kroki-plugin/.last-use`. The watchdog is intentionally NOT shipped in Plan 1 — Plan 5 introduces it.

## Common failures

| Symptom | Recovery |
|---------|----------|
| `pod-health.sh` exits 1 first try, succeeds on retry | Pod was cold-starting. Normal. |
| `pod-health.sh` exits 1 repeatedly, circuit opens | Check `~/kroki/kroki.sh logs` for crash, OOM, port conflict. Fix root cause, then clear circuit per "Circuit breaker" above. |
| Port 8000 in use by another process | `ss -tlnp \| grep :8000` to identify the holder. Stop it manually — `pod-health.sh` will NOT auto-kill. |
| `podman pull` fails (offline) | Pod cannot be (re)started. Wait for connectivity, then `kroki.sh up`. |
| One companion container crashed (e.g. `kroki-mermaid`) | `podman restart kroki-mermaid`. If still failing: full pod restart via `kroki.sh down && kroki.sh up`. |
| Symbolator renders fail with weird errors | The patched gateway image (`~/kroki/Dockerfile.kroki-patched`) must be the one running. Verify with `podman images \| grep kroki-gateway`. |

## Manual diagnostics

```bash
# Pod status
~/kroki/kroki.sh status

# Container-by-container
podman ps --filter pod=kroki --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Gateway health (raw)
curl -v -m 5 http://localhost:8000

# Gateway log tail
podman logs --tail 50 kroki-gateway

# All container logs
podman pod logs --tail 30 kroki

# Disk usage of pod
podman system df
```

## Restart safety

The plugin's `pod-health.sh` is the only thing that should auto-restart the pod. Do NOT add other auto-restart triggers — the circuit breaker exists to prevent restart loops. If you need to restart manually, just run `~/kroki/kroki.sh down && ~/kroki/kroki.sh up` directly; that bypasses the counter.

## Active-editor lock (planned, Plan 5)

When `~/.kroki-plugin/.active-editor.lock` exists and is fresh (<2h), DO NOT restart the pod — it would interrupt the user's GUI session. The watchdog and version-check upgrade flow both check this lock before any disruptive action.
