# Phase 6: Analytics and Observability - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Add per-topic analytics (message rate counters, payload histograms for numeric values), structured JSON logging via structlog replacing print/stdlib, Prometheus-compatible /metrics endpoint, topic favorites/bookmarks, and retained message indicator. Analytics UI components in the dashboard.

</domain>

<decisions>
## Implementation Decisions

### Per-Topic Analytics
- Rolling message rate counters per topic (messages/min, messages/hour)
- Tracked in-memory via deque of timestamps per topic
- Payload value histograms for numeric JSON payloads (min, max, avg, count)
- Analytics data exposed via /api/v1/analytics/topics endpoint
- Dashboard widget shows top-N topics by message rate

### Structured Logging
- structlog replacing all print() and stdlib logging calls
- JSON output format for production, colored console for development
- Request context (method, path, status, duration) on every log line
- MQTT event context (topic, qos, retain) on message logs
- Log level configurable via LOG_LEVEL env var (existing)

### Prometheus Metrics
- /metrics endpoint returning Prometheus text format
- Counters: mqtt_messages_total, rule_firings_total, webhook_deliveries_total, alerts_total
- Gauges: mqtt_connected (0/1), active_rules, websocket_clients
- Histograms: webhook_delivery_duration_seconds
- Labels: topic (on message counter), rule_id (on firing counter), status (on webhook)

### Topic Favorites/Bookmarks
- User can star/bookmark topics for quick access
- Stored in SQLite (user_id, topic, created_at)
- Bookmarked topics shown at top of topic list
- Toggle via /api/v1/topics/<topic>/bookmark endpoint

### Retained Message Indicator
- Messages with retain=True get visual indicator in message list
- Small "R" badge or pin icon next to retained messages
- Already tracked in message storage (retain flag exists in database)

### Claude's Discretion
- Exact structlog processor chain configuration
- Prometheus client library choice (prometheus_client is standard)
- Analytics data retention/rollover policy
- Histogram bucket boundaries for numeric payloads
- Topic bookmark UI placement

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- mqttui/events.py — blinker signals for hooking into message flow
- mqttui/database.py — MessageDatabase with topic stats
- mqttui/routes/api_v1.py — API v1 blueprint for analytics endpoints
- mqttui/socketio_batch.py — batch emitter for real-time analytics updates
- templates/index.html — Dashboard tab for analytics widgets

### Integration Points
- mqtt_message_received signal — analytics subscriber
- /api/v1/topics — extend with analytics data
- templates/index.html — add analytics widgets to dashboard
- requirements.txt — structlog, prometheus_client
- mqttui/app.py — structlog configuration, metrics endpoint

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard observability patterns

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>
