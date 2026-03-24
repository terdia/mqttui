"""Per-topic analytics engine with rate counters and numeric payload histograms.

Provides real-time message rate tracking and statistical aggregation for
numeric JSON payload fields. Subscribes to mqtt_message_received signal
for automatic data collection.
"""
import json
import logging
import time
from collections import deque

from mqttui.events import mqtt_message_received

logger = logging.getLogger(__name__)

# Maximum timestamps stored per topic (automatic memory bounding)
MAX_TIMESTAMPS = 10000


class TopicAnalytics:
    """Track per-topic message rates and numeric payload histograms.

    Data structures per topic:
        _timestamps: dict[str, deque] -- rolling window of message timestamps
        _histograms: dict[str, dict] -- per-topic numeric stats per field
            Each field: {min, max, sum, count}
    """

    def __init__(self):
        self._timestamps: dict[str, deque] = {}
        self._histograms: dict[str, dict] = {}

    def record(self, topic: str, payload: str, timestamp: float):
        """Record a message for a topic.

        Args:
            topic: MQTT topic string
            payload: Raw payload string (may be JSON)
            timestamp: Unix timestamp of message receipt
        """
        # Track timestamp for rate calculation
        if topic not in self._timestamps:
            self._timestamps[topic] = deque(maxlen=MAX_TIMESTAMPS)
        # Ensure timestamp is a Unix float for rate calculations
        if hasattr(timestamp, 'timestamp'):
            timestamp = timestamp.timestamp()
        self._timestamps[topic].append(timestamp)

        # Try to extract numeric fields from JSON payload
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                for field_name, value in data.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        self._update_histogram(topic, field_name, float(value))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    def _update_histogram(self, topic: str, field_name: str, value: float):
        """Update histogram stats for a numeric field."""
        if topic not in self._histograms:
            self._histograms[topic] = {}

        if field_name not in self._histograms[topic]:
            self._histograms[topic][field_name] = {
                "min": value,
                "max": value,
                "sum": value,
                "count": 1,
            }
        else:
            stats = self._histograms[topic][field_name]
            stats["min"] = min(stats["min"], value)
            stats["max"] = max(stats["max"], value)
            stats["sum"] += value
            stats["count"] += 1

    def get_rate(self, topic: str, window: int = 60) -> float:
        """Count messages within the last `window` seconds.

        Args:
            topic: MQTT topic string
            window: Time window in seconds (default 60)

        Returns:
            Number of messages received within the window.
        """
        if topic not in self._timestamps:
            return 0.0

        cutoff = time.time() - window
        count = sum(1 for ts in self._timestamps[topic] if ts >= cutoff)
        return float(count)

    def get_topic_stats(self, topic: str) -> dict:
        """Return full stats dict for a single topic.

        Returns:
            Dict with topic, rate_per_min, rate_per_hour, message_count, histograms
        """
        ts_deque = self._timestamps.get(topic, deque())
        return {
            "topic": topic,
            "rate_per_min": self.get_rate(topic, 60),
            "rate_per_hour": self.get_rate(topic, 3600),
            "message_count": len(ts_deque),
            "histograms": self._histograms.get(topic, {}),
        }

    def get_all_stats(self, limit: int = 20) -> list:
        """Return stats for all tracked topics, sorted by rate_per_min descending.

        Args:
            limit: Maximum number of topics to return (default 20)

        Returns:
            List of topic stats dicts.
        """
        all_topics = list(self._timestamps.keys())
        stats_list = [self.get_topic_stats(t) for t in all_topics]
        stats_list.sort(key=lambda s: s["rate_per_min"], reverse=True)
        return stats_list[:limit]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_analytics = None


def get_analytics() -> TopicAnalytics:
    """Return the module-level TopicAnalytics singleton."""
    global _analytics
    if _analytics is None:
        _analytics = TopicAnalytics()
    return _analytics


# ---------------------------------------------------------------------------
# Signal subscriber
# ---------------------------------------------------------------------------

def _on_mqtt_message(sender, **kwargs):
    """Handle mqtt_message_received signal -- record message in analytics."""
    get_analytics().record(
        kwargs["topic"],
        kwargs["payload"],
        kwargs["timestamp"],
    )
