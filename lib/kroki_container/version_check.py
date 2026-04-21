"""Kroki daily version-check. Tier-1 auto-pull + Tier-2 notify with 24h auto-defer."""

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from typing import Optional

from lib.kroki_container import common
from lib.kroki_session.lock import read_lock, is_stale

logger = logging.getLogger("kroki_container.version_check")

DEFERRED_FILE = ".upgrade-deferred.json"
BASELINE_FILE = ".version-baseline.json"
UPGRADE_IN_PROGRESS_FILE = ".upgrade-in-progress"
NOTIFY_COOLDOWN_SECONDS = 86400  # 24h auto-defer after notify
SKIP_DEFER_UNTIL = 4102444800    # 2100-01-01 epoch — effectively forever


def discover_pod_images(pod_name: str = "kroki") -> list:
    """Return the list of image refs in the pod's containers."""
    try:
        r = subprocess.run(
            ["podman", "pod", "inspect", pod_name],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if r.returncode != 0:
            logger.warning("podman pod inspect failed: %s", r.stderr.strip())
            return []
        data = json.loads(r.stdout)
        if isinstance(data, list) and data:
            data = data[0]
        refs = []
        for c in data.get("Containers", []):
            ref = c.get("Image")
            if ref and ref not in refs:
                refs.append(ref)
        return refs
    except Exception as e:
        logger.warning("discover_pod_images failed: %s", e)
        return []


def inspect_local_digest(image_ref: str) -> Optional[str]:
    """Return the sha256 digest of the local image, or None if not pulled."""
    try:
        r = subprocess.run(
            ["podman", "image", "inspect", image_ref, "--format", "{{.Digest}}"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if r.returncode != 0:
            return None
        digest = r.stdout.strip()
        if digest.startswith("sha256:"):
            return digest
        return None
    except Exception as e:
        logger.warning("inspect_local_digest(%s) failed: %s", image_ref, e)
        return None


def is_upstream(image_ref: str) -> bool:
    """True iff the image was pulled from a registry (has a Digest). Locally-built
    images have no registry digest."""
    return inspect_local_digest(image_ref) is not None and not image_ref.startswith("localhost/")


def compute_digest_set_hash(digests: dict) -> str:
    """Stable hash over {image: digest} for defer-scoping."""
    items = sorted(digests.items())
    h = hashlib.sha256()
    for k, v in items:
        h.update(k.encode())
        h.update(b"\0")
        h.update((v or "").encode())
        h.update(b"\0")
    return h.hexdigest()


def compute_changed_images(baseline: dict, current: dict) -> dict:
    """Return {image: (baseline_digest, current_digest)} for entries where
    current digest differs from baseline (or baseline didn't have the image)."""
    changed = {}
    for image, new_digest in current.items():
        old_digest = baseline.get(image)
        if old_digest != new_digest:
            changed[image] = (old_digest, new_digest)
    return changed


def pull_image(image_ref: str) -> bool:
    """podman pull the image. True on success."""
    try:
        r = subprocess.run(
            ["podman", "pull", image_ref],
            capture_output=True, text=True, check=False, timeout=180,
        )
        if r.returncode == 0:
            return True
        logger.warning("podman pull %s failed: %s", image_ref, r.stderr.strip())
        return False
    except Exception as e:
        logger.warning("pull_image(%s) exception: %s", image_ref, e)
        return False


def cycle() -> int:
    """One version-check cycle. Always returns 0 (systemd ExecStart contract)."""
    cfg = common.load_config()
    if not cfg["version_check"]["enabled"]:
        logger.info("version_check disabled in config — noop")
        return 0

    if not common.network_available():
        logger.info("offline — skipping cycle")
        return 0

    if common.read_state(UPGRADE_IN_PROGRESS_FILE) is not None:
        logger.info("upgrade in progress — skipping cycle")
        return 0

    # Editor-lock defer
    try:
        lock = read_lock()
        if lock and not is_stale(lock):
            logger.info("editor lock held — skipping cycle")
            return 0
    except Exception as e:
        logger.warning("lock check failed: %s — continuing", e)

    pod_images = discover_pod_images("kroki")
    upstream = [ref for ref in pod_images if is_upstream(ref)]

    baseline = common.read_state(BASELINE_FILE) or {}

    # Tier 1: pull + inspect → current digest map
    current: dict = {}
    for ref in upstream:
        if pull_image(ref):
            d = inspect_local_digest(ref)
            if d:
                current[ref] = d
        else:
            logger.warning("pull failed for %s — carrying baseline digest forward", ref)
            if ref in baseline:
                current[ref] = baseline[ref]

    # Baseline reflects the current local-cache state, always.
    common.write_state(BASELINE_FILE, current)

    changed = compute_changed_images(baseline, current)
    if not changed:
        return 0

    # Defer check
    deferred = common.read_state(DEFERRED_FILE)
    now = int(time.time())
    current_dsh = compute_digest_set_hash(current)
    if isinstance(deferred, dict) \
            and deferred.get("deferred_until", 0) > now \
            and deferred.get("digest_set_hash") == current_dsh:
        logger.info("upgrade deferred — suppressing notification")
        return 0

    # Tier 2 notify
    body_lines = _format_change_summary(changed)
    common.notify_and_log(
        "info",
        "Kroki upgrade available",
        body_lines,
        suggested_cmds=[
            "kroki-upgrade",
            "kroki-version-check defer 7d",
            "kroki-version-check skip",
        ],
    )

    # Auto-defer post-notify: nag once per 24h by default
    common.write_state(DEFERRED_FILE, {
        "digest_set_hash": current_dsh,
        "deferred_until": now + NOTIFY_COOLDOWN_SECONDS,
    })
    return 0


def _format_change_summary(changed: dict) -> str:
    lines = [f"{len(changed)} image(s) changed upstream:"]
    for image, (old, new) in sorted(changed.items()):
        short = image.split("/")[-1]
        if old is None:
            lines.append(f"  {short}: new (digest {new[:17]}…)")
        else:
            lines.append(f"  {short}: {old[:17]}… → {new[:17]}…")
    return "\n".join(lines)


def cmd_defer(duration: str) -> int:
    try:
        seconds = common.parse_duration(duration)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    baseline = common.read_state(BASELINE_FILE) or {}
    dsh = compute_digest_set_hash(baseline)
    common.write_state(DEFERRED_FILE, {
        "digest_set_hash": dsh,
        "deferred_until": int(time.time()) + seconds,
    })
    print(f"Upgrade deferred {duration} for current digest set.")
    return 0


def cmd_skip() -> int:
    baseline = common.read_state(BASELINE_FILE) or {}
    dsh = compute_digest_set_hash(baseline)
    common.write_state(DEFERRED_FILE, {
        "digest_set_hash": dsh,
        "deferred_until": SKIP_DEFER_UNTIL,
    })
    print("Skip recorded. Will not notify for current digest set; a new upstream "
          "change cancels the skip automatically.")
    return 0


def cmd_status() -> int:
    baseline = common.read_state(BASELINE_FILE) or {}
    print(f"Baseline images: {len(baseline)}")
    for image, digest in sorted(baseline.items()):
        short = image.split("/")[-1]
        print(f"  {short}: {digest[:17]}…")
    deferred = common.read_state(DEFERRED_FILE)
    now = int(time.time())
    if isinstance(deferred, dict):
        until = deferred.get("deferred_until", 0)
        if until >= SKIP_DEFER_UNTIL:
            print("Deferred: skipped (permanent until upstream change)")
        elif until > now:
            remaining = until - now
            print(f"Deferred: {remaining // 3600}h {(remaining % 3600) // 60:02d}m remaining")
        else:
            print("Deferred: expired")
    else:
        print("Deferred: no")
    return 0


def main(argv: Optional[list] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        return cycle()
    sub, rest = argv[0], argv[1:]
    if sub == "defer":
        if not rest:
            print("USAGE: kroki-version-check defer <duration>", file=sys.stderr)
            return 2
        return cmd_defer(rest[0])
    if sub == "skip":
        return cmd_skip()
    if sub == "status":
        return cmd_status()
    print(f"Unknown subcommand: {sub}", file=sys.stderr)
    print("Subcommands: defer <dur> | skip | status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
