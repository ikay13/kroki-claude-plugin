"""Kroki container idle watchdog. Tier 1 notify (2h default), Tier 2 auto-stop (6h default)."""

import json
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


def cmd_snooze(duration: str) -> int:
    try:
        seconds = common.parse_duration(duration)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    until = int(time.time()) + seconds
    common.write_state(SNOOZE_FILE, until)
    print(f"Snoozed until {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(until))}")
    return 0


def cmd_ignore() -> int:
    return cmd_snooze("24h")


def cmd_unsnooze() -> int:
    common.clear_state(SNOOZE_FILE)
    print("Snooze cleared.")
    return 0


def cmd_stop() -> int:
    try:
        r = subprocess.run([KROKI_SH, "down"], timeout=60)
        # Log explicit user stop (for post-mortem)
        common.notify_and_log("info", "Kroki pod stopped (user)",
                              "User ran `kroki-watchdog stop`; pod is now down.")
        return r.returncode
    except Exception as e:
        print(f"ERROR: kroki.sh down failed: {e}", file=sys.stderr)
        return 1


def cmd_status() -> int:
    now = int(time.time())
    last_use = common.read_state(LAST_USE_FILE) or 0
    if isinstance(last_use, str):
        try:
            last_use = int(last_use.strip())
        except Exception:
            last_use = 0
    idle_sec = max(0, now - last_use) if last_use else 0
    print(f"Pod idle: {_humanize_duration(idle_sec)} (last-use epoch: {last_use})")

    snooze = common.read_state(SNOOZE_FILE)
    if snooze:
        remaining = snooze - now if isinstance(snooze, int) else 0
        if remaining > 0:
            print(f"Snoozed: {_humanize_duration(remaining)} remaining")
        else:
            print("Snoozed: expired (will clear on next cycle)")
    else:
        print("Snoozed: no")

    state = read_tier_fired_state()
    print(f"Tier1 fired: {state['tier1_fired_at']}")
    print(f"Tier2 fired: {state['tier2_fired_at']}")
    return 0


def main(argv: Optional[list] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        return cycle()
    sub = argv[0]
    rest = argv[1:]
    if sub == "snooze":
        if not rest:
            print("USAGE: kroki-watchdog snooze <duration>", file=sys.stderr)
            return 2
        return cmd_snooze(rest[0])
    if sub == "ignore":
        return cmd_ignore()
    if sub == "unsnooze":
        return cmd_unsnooze()
    if sub == "stop":
        return cmd_stop()
    if sub == "status":
        return cmd_status()
    print(f"Unknown subcommand: {sub}", file=sys.stderr)
    print("Subcommands: snooze <dur> | ignore | unsnooze | stop | status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
