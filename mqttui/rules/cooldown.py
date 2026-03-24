"""Per-rule alert cooldown tracker for deduplication.

Prevents alert storms from sustained conditions by enforcing a minimum
interval between alert firings for each rule. Suppressed alerts are
counted so the suppression can be reported in AlertHistory.
"""
import time
from datetime import datetime, timedelta


class CooldownTracker:
    """In-memory per-rule cooldown tracker.

    Tracks the last time each rule fired and blocks subsequent firings
    within the cooldown window. Thread-safe for use from the webhook
    thread pool (GIL protects dict operations).
    """

    def __init__(self, default_seconds=300):
        """Initialize with a default cooldown window.

        Args:
            default_seconds: Default cooldown window in seconds (default 5 min).
        """
        self._last_fired = {}   # rule_id -> monotonic timestamp
        self._suppressed = {}   # rule_id -> suppressed count since last fire
        self._default = default_seconds

    def check(self, rule_id, cooldown_seconds=None):
        """Check if a rule is allowed to fire.

        Args:
            rule_id: The rule identifier.
            cooldown_seconds: Optional per-rule cooldown override.

        Returns:
            True if the rule is allowed to fire, False if suppressed.
        """
        window = cooldown_seconds if cooldown_seconds is not None else self._default
        now = time.monotonic()

        last = self._last_fired.get(rule_id)
        if last is None or (now - last) > window:
            # Allowed -- record firing and reset suppressed count
            self._last_fired[rule_id] = now
            self._suppressed[rule_id] = 0
            return True

        # Suppressed
        self._suppressed[rule_id] = self._suppressed.get(rule_id, 0) + 1
        return False

    def get_suppressed_count(self, rule_id):
        """Return the number of suppressed alerts since the last firing.

        Args:
            rule_id: The rule identifier.

        Returns:
            Number of suppressed alerts (0 if rule has never been suppressed).
        """
        return self._suppressed.get(rule_id, 0)

    def get_cooldown_until(self, rule_id, cooldown_seconds=None):
        """Return the datetime when the cooldown expires for a rule.

        Args:
            rule_id: The rule identifier.
            cooldown_seconds: Optional per-rule cooldown override.

        Returns:
            datetime when cooldown expires, or None if no active cooldown.
        """
        window = cooldown_seconds if cooldown_seconds is not None else self._default
        last = self._last_fired.get(rule_id)
        if last is None:
            return None

        elapsed = time.monotonic() - last
        remaining = window - elapsed
        if remaining <= 0:
            return None

        return datetime.utcnow() + timedelta(seconds=remaining)


# Module-level singleton used by the action executor
cooldown_tracker = CooldownTracker()
