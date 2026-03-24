---
phase: 06-analytics-and-observability
verified: 2026-03-24T12:00:00Z
status: gaps_found
score: 9/10 must-haves verified
re_verification: false
gaps:
  - truth: "ANLYT-03 — Analytics time-series queries via SQLite JSON1 extension"
    status: failed
    reason: "REQUIREMENTS.md specifies 'Analytics time-series queries via SQLite JSON1 extension'. The implementation delivers in-memory deque-based rate counters and REST API endpoints — there are no SQLite JSON1 queries anywhere in the codebase. Plan 01 claimed ANLYT-03 as fulfilled by the REST analytics query layer, which is a scope substitution not a fulfillment of the original requirement."
    artifacts:
      - path: "mqttui/analytics.py"
        issue: "Uses collections.deque in-memory storage only; no SQLite JSON1 query logic"
      - path: "mqttui/routes/analytics.py"
        issue: "Reads from in-memory TopicAnalytics singleton, not persisted SQLite time-series"
    missing:
      - "SQLite JSON1-based time-series query: query stored messages by topic+time range using json_extract on payload column"
      - "REST endpoint accepting time-range params (e.g., ?start=&end=) backed by SQLite JSON1 for historical analytics"
      - "Tests exercising SQLite JSON1 time-series query paths"
human_verification:
  - test: "Visit the Analytics tab in a running browser session"
    expected: "Top Topics widget loads and shows per-topic msg/min and msg/hour rates; clicking a topic reveals histogram stats; widget refreshes every 5 seconds without page reload"
    why_human: "Auto-refresh timing, Alpine.js reactive update, and visual rendering cannot be verified from static file analysis"
  - test: "Send a few MQTT messages to topics with numeric JSON payloads (e.g. {\"temperature\": 22.5})"
    expected: "Analytics widget updates within 5 seconds showing the new topic with rate and histogram data"
    why_human: "End-to-end flow through MQTT client -> signal -> analytics engine -> REST API -> UI requires a live environment"
  - test: "Star/bookmark a topic via the message list star icon"
    expected: "Star turns yellow immediately (optimistic UI), topic appears with a star indicator at top of topic filter dropdown on next load"
    why_human: "Alpine.js reactive state and sorted dropdown require browser rendering"
  - test: "Receive a retained MQTT message (retain flag = true)"
    expected: "Message appears in the list with a small amber 'R' badge next to the topic name"
    why_human: "Requires live MQTT broker interaction and visual badge rendering"
  - test: "Scrape /metrics in a terminal: curl http://localhost:5000/metrics"
    expected: "Returns Prometheus text format with mqtt_messages_total, rule_firings_total, mqtt_connected, websocket_clients counters/gauges; no authentication required"
    why_human: "Unauthenticated scrape and Prometheus text format correctness best verified against running server"
---

# Phase 6: Analytics and Observability — Verification Report

**Phase Goal:** Users and operators can understand what their MQTT infrastructure is doing, both in the UI and in production logs
**Verified:** 2026-03-24T12:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Per-topic message rate counters update in real-time in the UI for all active topics | VERIFIED | `templates/partials/analytics.html` renders `rate_per_min` and `rate_per_hour` via 5s setInterval fetch to `/api/v1/analytics/topics`; `mqttui/analytics.py` TopicAnalytics.get_rate() computes from deque timestamps wired to mqtt_message_received signal |
| 2 | Numeric payload values for a topic are displayed as a histogram showing min/max/avg/count | VERIFIED | `analytics.html` renders per-field histogram stats via Alpine.js x-for loop on `selectedHistograms`; `analytics.py` accumulates per-field min/max/sum/count from JSON payloads |
| 3 | Application logs are structured JSON (structlog) and include request context on every log line | VERIFIED | `mqttui/logging_config.py` implements configure_logging() with ConsoleRenderer (debug) and JSONRenderer (prod); wired in `app.py` line 76 via `configure_logging(debug=..., log_level=...)`; replaces stdlib logging.basicConfig entirely |
| 4 | A Prometheus scrape of /metrics returns message rate, active connections, and rule fire counts | VERIFIED | `mqttui/routes/metrics.py` defines mqtt_messages_total, rule_firings_total, mqtt_connected, websocket_clients; endpoint at /metrics unauthenticated; signal subscribers wired in app.py lines 165-170 |
| 5 | User can bookmark a topic as a favorite; retained messages are visually distinguished | VERIFIED | `templates/index.html` line 175 x-show="msg.retain" amber badge; line 178-181 star toggle button with toggleFavorite()/isFavorite(); `api_v1.py` bookmark toggle and favorites list endpoints wired to TopicFavorite model |

**Score from ROADMAP Success Criteria:** 5/5 truths verified

---

## Required Artifacts — Three-Level Verification

### Plan 01: Analytics Engine (ANLYT-01, ANLYT-02, ANLYT-03)

| Artifact | Exists | Substantive | Wired | Status | Details |
|----------|--------|-------------|-------|--------|---------|
| `mqttui/analytics.py` | Yes | Yes — 148 lines, TopicAnalytics class, get_rate(), get_topic_stats(), get_all_stats(), singleton, signal subscriber | Yes — wired in app.py line 161-162 | VERIFIED | All exports present: TopicAnalytics, get_analytics, _on_mqtt_message |
| `mqttui/routes/analytics.py` | Yes | Yes — analytics_bp Blueprint, /api/v1/analytics/topics, /api/v1/analytics/topics/<path:topic>, @login_required, get_analytics() calls | Yes — registered in app.py line 146 | VERIFIED | Full implementation, not a stub |
| `tests/test_analytics.py` | Yes | Yes — 164 lines, 15 tests across 3 test classes | N/A — test file | VERIFIED | 8 unit + 4 API integration + 3 partial route tests; all 15 pass |

### Plan 02: Structured Logging + Prometheus (ANLYT-04, ANLYT-05)

| Artifact | Exists | Substantive | Wired | Status | Details |
|----------|--------|-------------|-------|--------|---------|
| `mqttui/logging_config.py` | Yes | Yes — 54 lines, configure_logging() with shared processors, JSONRenderer/ConsoleRenderer switch, ProcessorFormatter, root handler setup | Yes — imported and called in app.py line 8, 76 | VERIFIED | Full structlog implementation |
| `mqttui/routes/metrics.py` | Yes | Yes — 54 lines, metrics_bp Blueprint, 4 Counters, 3 Gauges, 1 Histogram, /metrics endpoint, 3 signal subscriber functions | Yes — registered app.py line 145, subscribers wired lines 165-170 | VERIFIED | Note: ACTIVE_RULES gauge defined but never set (see anti-patterns) |
| `tests/test_observability.py` | Yes | Yes — 84 lines, 8 tests (3 structlog config + 5 metrics endpoint) | N/A | VERIFIED | All 8 pass |

### Plan 03: UX Features (UX-01, UX-02)

| Artifact | Exists | Substantive | Wired | Status | Details |
|----------|--------|-------------|-------|--------|---------|
| `mqttui/models.py` | Yes | Yes — TopicFavorite class with user_id, topic, UniqueConstraint('user_id','topic'), to_dict() | Yes — imported in api_v1.py line 16; auto-discovered by sa.create_all() in app.py | VERIFIED | Correct schema with per-user uniqueness constraint |
| `mqttui/routes/api_v1.py` | Yes | Yes — toggle_bookmark(), get_favorites(), GET /topics annotated with is_favorite; all @login_required | Yes — part of api_v1_bp registered in app.py line 142 | VERIFIED | Toggle correctly creates/deletes; 201 on create, 200 on delete |
| `templates/index.html` | Yes | Yes — x-show="msg.retain" badge at line 175; toggleFavorite/isFavorite at lines 178-181; analytics tab button+panel at lines 144-215 | Yes — Alpine.js component calls /api/v1/topics/favorites implicitly via script.js | VERIFIED | retain and bookmark UI both present |
| `tests/test_ux_features.py` | Yes | Yes — 61 lines, 5 tests for bookmark CRUD and auth | N/A | VERIFIED | All 5 pass |

### Plan 04: Analytics Dashboard UI (ANLYT-01 UI, ANLYT-02 UI)

| Artifact | Exists | Substantive | Wired | Status | Details |
|----------|--------|-------------|-------|--------|---------|
| `templates/partials/analytics.html` | Yes | Yes — 101 lines, analyticsWidget() Alpine.js component, rate_per_min display, histogram detail, 5s setInterval auto-refresh, fetch to /api/v1/analytics/topics | Yes — rendered by /partials/analytics route; fetches live API | VERIFIED | Contains rate_per_min, histograms, selectedHistograms, destroy() cleanup |
| `templates/index.html` (analytics tab) | Yes | Yes — Analytics tab button with htmx.ajax lazy-load, analytics-panel div, analyticsLoaded flag | Yes — tab button calls htmx.ajax to load partial on first click | VERIFIED | Matches expected lazy-load pattern |
| `mqttui/routes/main.py` | Yes | Yes — analytics_partial() route at /partials/analytics, @login_required, render_template('partials/analytics.html') | Yes — registered via main_bp in app.py line 139 | VERIFIED | Route at lines 150-154 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `mqttui/analytics.py` | `mqttui/events.py` (mqtt_message_received) | Signal subscriber _on_mqtt_message connected in app.py | WIRED | app.py lines 161-162: `from mqttui.analytics import _on_mqtt_message as _on_analytics_message; mqtt_message_received.connect(_on_analytics_message)` — wired in app.py not analytics.py (plan expected the connect call in analytics.py, but app.py is the correct pattern) |
| `mqttui/routes/analytics.py` | `mqttui/analytics.py` | get_analytics() calls | WIRED | analytics.py line 13: `from mqttui.analytics import get_analytics`; used in get_topics() and get_topic() |
| `mqttui/app.py` | `mqttui/routes/analytics.py` | blueprint registration | WIRED | app.py lines 137, 146: import and register analytics_bp |
| `mqttui/app.py` | `mqttui/logging_config.py` | configure_logging() call | WIRED | app.py lines 8, 76 |
| `mqttui/app.py` | `mqttui/routes/metrics.py` | blueprint registration | WIRED | app.py lines 136, 145 |
| `mqttui/routes/metrics.py` | `prometheus_client` | generate_latest() | WIRED | metrics.py line 6: imported; line 36: returned in Response |
| `mqttui/routes/api_v1.py` | `mqttui/models.py` | TopicFavorite queries | WIRED | api_v1.py line 16: import; lines 147, 170, 196, 204: queries |
| `templates/index.html` | `msg.retain` | Alpine.js x-show conditional badge | WIRED | index.html line 175: `x-show="msg.retain"` |
| `templates/index.html` | `/partials/analytics` | htmx.ajax on first tab click (Alpine @click) | WIRED | index.html line 144: `htmx.ajax('GET', '/partials/analytics', ...)` in @click handler — uses htmx.ajax imperatively rather than hx-get attribute; functionally identical |
| `templates/partials/analytics.html` | `/api/v1/analytics/topics` | fetch() in fetchAnalytics() | WIRED | analytics.html line 80: `fetch('/api/v1/analytics/topics?limit=10')` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ANLYT-01 | 06-01, 06-04 | Per-topic message rate counters displayed in UI | SATISFIED | rate_per_min and rate_per_hour computed by TopicAnalytics, served via REST, rendered in analytics.html |
| ANLYT-02 | 06-01, 06-04 | Payload value histograms for numeric payloads | SATISFIED | _histograms dict tracks min/max/sum/count per JSON field; displayed in analytics.html histogram detail section |
| ANLYT-03 | 06-01 | Analytics time-series queries via SQLite JSON1 extension | BLOCKED | REQUIREMENTS.md specifies SQLite JSON1 time-series queries. Implementation delivers in-memory deque analytics and REST endpoints only. No json_extract, no time-range queries against persisted message store exist anywhere in the codebase. Plan 01 mis-mapped ANLYT-03 to the general REST analytics query layer. |
| ANLYT-04 | 06-02 | Structured JSON logging replacing print/stdlib logging (structlog) | SATISFIED | configure_logging() in logging_config.py; JSONRenderer in prod, ConsoleRenderer in dev; wired in app.py; 3 tests pass |
| ANLYT-05 | 06-02 | Prometheus-compatible /metrics endpoint | SATISFIED | /metrics endpoint unauthenticated; counters mqtt_messages_total, rule_firings_total, webhook_deliveries_total, alerts_total; gauges mqtt_connected, websocket_clients; 5 tests pass |
| UX-01 | 06-03 | Topic favorites/bookmarks for quick access | SATISFIED | TopicFavorite model, toggle_bookmark(), get_favorites(), is_favorite annotation on GET /topics, star UI in message list; 4 tests pass |
| UX-02 | 06-03 | Retained message indicator on messages displayed in UI | SATISFIED | retain kwarg forwarded in msg_data dict (app.py line 26), x-show="msg.retain" badge in index.html line 175 |

### ANLYT-03 Gap Analysis

The requirement ANLYT-03 as written in REQUIREMENTS.md is:
> "Analytics time-series queries via SQLite JSON1 extension"

What was implemented:
- In-memory deque-based rate counters with rolling window
- REST endpoints /api/v1/analytics/topics (in-memory aggregates)

What was NOT implemented:
- Any SQLite JSON1 (json_extract) query against persisted messages
- Time-range parameter support backed by the MessageDatabase
- Historical analytics beyond the current runtime window

Plan 01's success criteria and objective redefined ANLYT-03 as "analytics queryable via REST API with topic filtering" — this is a narrower scope than the specification. The plan author likely treated the in-memory REST layer as sufficient to claim ANLYT-03, but the requirement explicitly calls for SQLite JSON1 time-series queries.

**Impact:** ANLYT-03 does not affect the ROADMAP's 5 Success Criteria (none of the 5 success criteria mention SQLite JSON1). The Success Criteria goal is fully met. ANLYT-03 is a formal requirement not reflected in the success criteria.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `mqttui/routes/metrics.py` | 19 | `ACTIVE_RULES = Gauge('active_rules', ...)` defined but never set in /metrics endpoint or anywhere else | Warning | The gauge will always report 0 to Prometheus scrapers; operators cannot monitor active rule count |
| `mqttui/app.py` | 131 | `# TODO: Remove legacy /api/ routes in Phase 5 after frontend migrates to /api/v1/` | Info | Leftover TODO from Phase 5; legacy routes still present but non-blocking for Phase 6 goals |

---

## Human Verification Required

### 1. Analytics Widget Real-Time Update

**Test:** Open the dashboard in a browser, click the Analytics tab, then publish MQTT messages with numeric JSON payloads (e.g., `{"temperature": 22.5}`)
**Expected:** The Top Topics widget shows the new topic within 5 seconds with rate_per_min > 0; clicking the topic shows the histogram min/max/avg/count for "temperature"
**Why human:** setInterval 5s auto-refresh, Alpine.js reactive data binding, and histogram click-expand behavior require a live browser

### 2. Retained Message Badge

**Test:** Publish a retained MQTT message (retain=true) to a test topic
**Expected:** The message appears in the live message list with an amber "R" badge immediately to the right of the topic name
**Why human:** Requires live MQTT broker with retain flag support and visual badge rendering

### 3. Topic Bookmark Star Toggle

**Test:** In the message list, click the star icon next to a message topic
**Expected:** Star turns yellow immediately (optimistic), subsequent topic filter dropdown shows that topic with a star at the top of the list
**Why human:** Optimistic UI state, Alpine.js x-html entity rendering, and dropdown sort order require browser interaction

### 4. Structured Log Output Format

**Test:** Start the app without DEBUG=true, send a request, observe stdout
**Expected:** Each log line is a single-line JSON object with `event`, `level`, `timestamp`, `logger` keys at minimum
**Why human:** Terminal output format cannot be reliably captured from static analysis

### 5. Prometheus Metrics Scrape

**Test:** `curl http://localhost:5000/metrics` (no auth headers)
**Expected:** Returns HTTP 200 with content-type text/plain; body contains `# HELP mqtt_messages_total`, `# HELP rule_firings_total`, `mqtt_connected` gauge
**Why human:** Unauthenticated endpoint behavior and Prometheus text format correctness best confirmed against running server

---

## Gaps Summary

**1 formal requirement not fulfilled: ANLYT-03**

ANLYT-03 requires "Analytics time-series queries via SQLite JSON1 extension." The implementation provides only in-memory analytics (deque-based rolling window counters). No SQLite JSON1 query exists in the codebase — not in `mqttui/analytics.py`, `mqttui/routes/analytics.py`, or `mqttui/database.py`.

Plan 01 claimed ANLYT-03 by reframing it as "analytics queryable via REST API with topic filtering" — this is scope substitution. The REST analytics endpoints query the in-memory TopicAnalytics singleton, which loses all data on restart and cannot answer historical time-range queries.

**Separating formal requirement gap from phase goal achievement:**

The ROADMAP's 5 Success Criteria for Phase 6 do NOT include SQLite JSON1 time-series queries. All 5 success criteria are verifiably met. The phase goal ("Users and operators can understand what their MQTT infrastructure is doing") is substantially achieved.

ANLYT-03 represents a formal requirement that was not carried into the success criteria — it requires a separate remediation plan or explicit deferral decision.

**1 warning: ACTIVE_RULES gauge never populated**

The `active_rules` Gauge is defined in metrics.py but its value is never set in the /metrics handler or anywhere else. It will always return 0. This is a minor accuracy issue for Prometheus operators but does not block the phase goal.

---

_Verified: 2026-03-24T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
