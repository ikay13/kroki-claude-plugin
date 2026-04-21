"""Kroki container idle watchdog. Tier 1 notify (2h default), Tier 2 auto-stop (6h default)."""

import logging
import os
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


KROKI_SH = os.environ.get("KROKI_SH", os.path.expanduser("~/kroki/kroki.sh"))


def cycle() -> int:
    """One watchdog cycle. Returns 0 always (systemd ExecStart contract)."""
    cfg = common.load_config()
    if not cfg["watchdog"]["enabled"]:
        logger.info("watchdog disabled in config — noop")
        return 0

    # Editor-lock defer (silent)
    try:
        lock = read_lock()
        if lock and not is_stale(lock):
            logger.info("cycle skipped: editor lock held")
            return 0
    except Exception as e:
        logger.warning("lock check failed: %s — continuing cycle", e)

    # Upgrade-in-progress defer (silent)
    if common.read_state(UPGRADE_IN_PROGRESS_FILE) is not None:
        logger.info("cycle skipped: upgrade in progress")
        return 0

    # Snooze defer
    snooze_until = common.read_state(SNOOZE_FILE)
    now = int(time.time())
    if snooze_until is not None:
        if isinstance(snooze_until, int) and snooze_until > now:
            return 0
        else:
            common.clear_state(SNOOZE_FILE)

    # Read last-use
    last_use = common.read_state(LAST_USE_FILE)
    if last_use is None:
        logger.info("no .last-use yet — pod has never been touched; noop")
        return 0
    if not isinstance(last_use, int):
        try:
            last_use = int(str(last_use).strip())
        except ValueError:
            logger.warning(".last-use malformed — noop")
            return 0
    idle = compute_idle_seconds(last_use, now=now)

    # Tier-fired state, possibly reset
    state = read_tier_fired_state()
    state = maybe_reset_tier_state(last_use, state)

    tier1_secs = int(cfg["watchdog"]["tier1_hours"] * 3600)
    tier2_secs = int(cfg["watchdog"]["tier2_hours"] * 3600)

    if idle >= tier2_secs and state["tier2_fired_at"] is None:
        _fire_tier2(idle, now, state)
        return 0
    if idle >= tier1_secs and state["tier1_fired_at"] is None:
        _fire_tier1(idle, now, state, tier2_secs)
        return 0

    # Persist (may have been modified by reset)
    if state != read_tier_fired_state():
        write_tier_fired_state(state)
    return 0


def _humanize_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _fire_tier1(idle: int, now: int, state: dict, tier2_secs: int) -> None:
    cfg = common.load_config()
    tier2_hours = cfg["watchdog"]["tier2_hours"]
    title = f"Kroki pod idle {_humanize_duration(idle)}"
    body = (f"Pod has been idle for {_humanize_duration(idle)}. "
            f"Will auto-stop at {tier2_hours}h idle.")
    common.notify_and_log(
        "warning", title, body,
        suggested_cmds=[
            "kroki-watchdog snooze 1h",
            "kroki-watchdog stop",
        ],
    )
    state["tier1_fired_at"] = now
    write_tier_fired_state(state)


def _fire_tier2(idle: int, now: int, state: dict) -> None:
    title = f"Kroki pod auto-stopped"
    body = f"Pod was idle {_humanize_duration(idle)} and has been stopped. Next render will restart it."
    try:
        subprocess.run([KROKI_SH, "down"], check=False, timeout=60)
    except Exception as e:
        logger.error("kroki.sh down failed: %s", e)
    common.notify_and_log("info", title, body)
    state["tier2_fired_at"] = now
    write_tier_fired_state(state)
