"""Tests for the per-topic analytics engine."""
import time
import json
import pytest

from mqttui.analytics import TopicAnalytics, get_analytics


class TestTopicAnalytics:
    """Unit tests for TopicAnalytics engine."""

    def setup_method(self):
        self.analytics = TopicAnalytics()

    def test_record_increments_message_count(self):
        """Test 1: record() increments message count for topic."""
        self.analytics.record("home/temp", '{"temperature": 22.5}', time.time())
        self.analytics.record("home/temp", '{"temperature": 23.0}', time.time())
        stats = self.analytics.get_topic_stats("home/temp")
        assert stats["message_count"] == 2

    def test_get_rate_per_minute(self):
        """Test 2: get_rate(topic, window=60) returns msgs in last 60s."""
        now = time.time()
        for i in range(5):
            self.analytics.record("sensor/a", "payload", now - i)
        rate = self.analytics.get_rate("sensor/a", window=60)
        assert rate == 5.0

    def test_get_rate_per_hour(self):
        """Test 3: get_rate(topic, window=3600) returns msgs in last hour."""
        now = time.time()
        for i in range(10):
            self.analytics.record("sensor/b", "payload", now - i * 60)
        rate = self.analytics.get_rate("sensor/b", window=3600)
        assert rate == 10.0

    def test_expired_timestamps_not_counted(self):
        """Test 4: Timestamps outside window are not counted."""
        now = time.time()
        # Record 3 messages: 2 within window, 1 expired
        self.analytics.record("sensor/c", "x", now - 120)  # 2 min ago (outside 60s)
        self.analytics.record("sensor/c", "x", now - 30)   # 30s ago (inside 60s)
        self.analytics.record("sensor/c", "x", now - 10)   # 10s ago (inside 60s)
        rate = self.analytics.get_rate("sensor/c", window=60)
        assert rate == 2.0

    def test_numeric_payload_updates_histogram(self):
        """Test 5: Numeric JSON payload updates histogram stats."""
        self.analytics.record("sensor/d", '{"temperature": 22.5}', time.time())
        self.analytics.record("sensor/d", '{"temperature": 25.0}', time.time())
        self.analytics.record("sensor/d", '{"temperature": 20.0}', time.time())
        stats = self.analytics.get_topic_stats("sensor/d")
        hist = stats["histograms"]["temperature"]
        assert hist["min"] == 20.0
        assert hist["max"] == 25.0
        assert hist["count"] == 3
        assert abs(hist["sum"] - 67.5) < 0.01

    def test_non_numeric_payload_does_not_crash(self):
        """Test 6: Non-numeric/non-JSON payloads are handled gracefully."""
        self.analytics.record("sensor/e", "not json", time.time())
        self.analytics.record("sensor/e", '{"status": "online"}', time.time())
        self.analytics.record("sensor/e", "", time.time())
        stats = self.analytics.get_topic_stats("sensor/e")
        assert stats["message_count"] == 3
        assert stats["histograms"] == {}

    def test_get_topic_stats_returns_full_dict(self):
        """Test 7: get_topic_stats() returns dict with rate and histogram data."""
        now = time.time()
        self.analytics.record("sensor/f", '{"humidity": 60}', now)
        stats = self.analytics.get_topic_stats("sensor/f")
        assert stats["topic"] == "sensor/f"
        assert "rate_per_min" in stats
        assert "rate_per_hour" in stats
        assert "message_count" in stats
        assert "histograms" in stats
        assert "humidity" in stats["histograms"]

    def test_get_all_stats_sorted_by_rate(self):
        """Test 8: get_all_stats() returns topics sorted by rate descending."""
        now = time.time()
        # Topic A: 1 message
        self.analytics.record("topic/a", "x", now)
        # Topic B: 3 messages (highest rate)
        for _ in range(3):
            self.analytics.record("topic/b", "x", now)
        # Topic C: 2 messages
        for _ in range(2):
            self.analytics.record("topic/c", "x", now)

        all_stats = self.analytics.get_all_stats(limit=20)
        assert len(all_stats) == 3
        assert all_stats[0]["topic"] == "topic/b"
        assert all_stats[1]["topic"] == "topic/c"
        assert all_stats[2]["topic"] == "topic/a"


class TestAnalyticsAPI:
    """Integration tests for analytics REST API endpoints."""

    def test_get_topics_returns_200(self, auth_client, app):
        """GET /api/v1/analytics/topics returns 200 with topics array."""
        # Seed some analytics data
        from mqttui.analytics import get_analytics
        analytics = get_analytics()
        now = time.time()
        analytics.record("test/topic", '{"value": 42}', now)

        resp = auth_client.get('/api/v1/analytics/topics')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "topics" in data["data"]
        assert isinstance(data["data"]["topics"], list)

    def test_get_single_topic_returns_200(self, auth_client, app):
        """GET /api/v1/analytics/topics/<topic> returns 200 with stats."""
        from mqttui.analytics import get_analytics
        analytics = get_analytics()
        now = time.time()
        analytics.record("home/sensor", '{"temp": 22}', now)

        resp = auth_client.get('/api/v1/analytics/topics/home/sensor')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["data"]["topic"] == "home/sensor"

    def test_get_unknown_topic_returns_404(self, auth_client):
        """GET /api/v1/analytics/topics/<unknown> returns 404."""
        resp = auth_client.get('/api/v1/analytics/topics/nonexistent/topic')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["status"] == "error"
        assert data["error"]["code"] == "NOT_FOUND"

    def test_unauthenticated_request_rejected(self, client):
        """Unauthenticated request to analytics API is rejected."""
        resp = client.get('/api/v1/analytics/topics')
        # Flask-Login redirects to login page (302) or returns 401
        assert resp.status_code in (302, 401)
