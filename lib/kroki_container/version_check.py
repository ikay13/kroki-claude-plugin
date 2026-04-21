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

DEFERRED_FILE = ".upgrade-deferred"
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
