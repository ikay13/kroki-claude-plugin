"""Kroki container idle watchdog. Tier 1 notify (2h default), Tier 2 auto-stop (6h default)."""

import logging
import subprocess
import sys
import time
from typing import Optional

from lib.kroki_container import common
from lib.kroki_session.lock import read_lock, is_stale

logger = logging.getLogger("kroki_container.watchdog")

TIER_FIRED_FILE = ".watchdog-tier-fired.json"
SNOOZE_FILE = ".watchdog-snooze-until"
UPGRADE_IN_PROGRESS_FILE = ".upgrade-in-progress"
LAST_USE_FILE = ".last-use"


def compute_idle_seconds(last_use: int, now: Optional[int] = None) -> int:
    """Return max(0, now - last_use). Clamps negative (clock skew) to 0."""
    if now is None:
        now = int(time.time())
    return max(0, now - last_use)


def read_tier_fired_state() -> dict:
    """Read .watchdog-tier-fired.json. Returns {tier1_fired_at, tier2_fired_at}
    with None defaults if absent or corrupt."""
    data = common.read_state(TIER_FIRED_FILE)
    if not isinstance(data, dict):
        return {"tier1_fired_at": None, "tier2_fired_at": None}
    return {
        "tier1_fired_at": data.get("tier1_fired_at"),
        "tier2_fired_at": data.get("tier2_fired_at"),
    }


def write_tier_fired_state(state: dict) -> None:
    common.write_state(TIER_FIRED_FILE, state)


def maybe_reset_tier_state(last_use: int, state: dict) -> dict:
    """If pod was touched since tier-1 fired, reset both tiers to None."""
    tier1 = state.get("tier1_fired_at")
    if tier1 is not None and last_use > tier1:
        return {"tier1_fired_at": None, "tier2_fired_at": None}
    return state
