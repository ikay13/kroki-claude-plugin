"""Pure decision helpers for upgrade.sh. The orchestrator is bash;
this module provides testable building blocks only."""

import subprocess
from typing import Optional


def compute_new_failures(baseline: dict, post: dict) -> list:
    """Return sorted list of fixtures that passed in baseline but fail post.
    Fixtures failing in both are pre-existing and do NOT count. A fixture
    missing from post (dropped for any reason) also counts as a regression."""
    result = []
    for fixture, state in baseline.items():
        if state == "pass":
            post_state = post.get(fixture)
            if post_state != "pass":
                result.append(fixture)
    return sorted(result)


def should_rollback(trigger: str, context: dict) -> tuple:
    """Return (rollback_bool, reason_string) for a trigger evaluation.

    Trigger IDs:
      A_pod_health — {"healthy": bool}
      B_smoke      — {"new_failures": [...]}
      C_pytest     — {"failed_count": int}

    NOTE (per design §4.4): this is a testing helper mirroring upgrade.sh's
    inline decision tree. If the bash orchestrator never imports it, the
    function still serves as the documented reference for which conditions
    trigger rollback.
    """
    if trigger == "A_pod_health":
        healthy = context.get("healthy", False)
        if not healthy:
            return (True, "pod failed to become healthy after restart")
        return (False, "pod healthy")
    if trigger == "B_smoke":
        new_failures = context.get("new_failures", [])
        if new_failures:
            return (True, f"smoke regression: {', '.join(sorted(new_failures))}")
        return (False, "no new smoke failures")
    if trigger == "C_pytest":
        failed = context.get("failed_count", 0)
        if failed > 0:
            return (True, f"pytest failed {failed} test(s)")
        return (False, "pytest clean")
    return (False, f"unknown trigger: {trigger}")


def is_upstream(image_ref: str) -> bool:
    """True iff the image has a registry digest (pulled from upstream).
    Locally-built images have no digest; `localhost/` prefix is always local."""
    if image_ref.startswith("localhost/"):
        return False
    try:
        r = subprocess.run(
            ["podman", "image", "inspect", image_ref, "--format", "{{.Digest}}"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if r.returncode != 0:
            return False
        return r.stdout.strip().startswith("sha256:")
    except Exception:
        return False
