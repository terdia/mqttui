---
phase: 06-analytics-and-observability
plan: 01
subsystem: analytics
tags: [analytics, rate-counters, histograms, deque, rest-api, blinker-signals]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "Flask app factory, event bus (blinker signals), test fixtures"
provides:
  - "TopicAnalytics engine with per-topic rate counters and numeric histograms"
  - "get_analytics() singleton for shared analytics access"
  - "REST API: GET /api/v1/analytics/topics and /api/v1/analytics/topics/<topic>"
  - "_on_mqtt_message signal subscriber for automatic data collection"
affects: [06-analytics-and-observability, 05-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns: [deque-based rolling window rate tracking, per-field numeric histogram accumulation]

key-files:
  created:
    - mqttui/analytics.py
    - mqttui/routes/analytics.py
  modified:
    - mqttui/app.py
    - tests/test_analytics.py

key-decisions:
  - "Used collections.deque(maxlen=10000) for automatic memory bounding of timestamp history"
  - "Histogram tracks per-field stats (min/max/sum/count) from top-level JSON keys only"
  - "No threading locks -- gevent greenlets are cooperative, no concurrent access risk"

patterns-established:
  - "Analytics singleton: get_analytics() returns module-level TopicAnalytics instance"
  - "Signal subscriber pattern: module-level _on_mqtt_message connected in create_app"

requirements-completed: [ANLYT-01, ANLYT-02, ANLYT-03]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 06 Plan 01: Analytics Engine Summary

**Per-topic analytics engine with deque-based rate counters, numeric JSON histogram accumulation, and REST API endpoints**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T10:37:26Z
- **Completed:** 2026-03-24T10:39:59Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- TopicAnalytics class with rolling-window rate counters (msgs/min, msgs/hour) using deque timestamps
- Per-topic numeric payload histograms tracking min/max/sum/count per JSON field
- REST API with two endpoints: top-N topics by rate, and single topic detail with path converter for MQTT slashes
- Signal subscriber wired to mqtt_message_received for automatic data collection

## Task Commits

Each task was committed atomically:

1. **Task 1: TopicAnalytics engine (TDD RED)** - `a5bbdec` (test)
2. **Task 1: TopicAnalytics engine (TDD GREEN)** - `2f5da0d` (feat)
3. **Task 2: Analytics REST API and app wiring** - `8dfd497` (feat)

_Note: Task 1 used TDD with separate RED/GREEN commits_

## Files Created/Modified
- `mqttui/analytics.py` - TopicAnalytics class with rate counters, histograms, singleton, signal subscriber
- `mqttui/routes/analytics.py` - Analytics REST API blueprint (/api/v1/analytics/*)
- `mqttui/app.py` - Blueprint registration and signal wiring for analytics
- `tests/test_analytics.py` - 12 tests (8 unit + 4 API integration)

## Decisions Made
- Used collections.deque(maxlen=10000) for automatic memory bounding of timestamp history
- Histogram tracks per-field stats (min/max/sum/count) from top-level JSON keys only -- nested objects skipped
- No threading locks since gevent greenlets are cooperative (no concurrent access risk)
- Path converter (`<path:topic>`) for MQTT topics containing slashes in URL routing

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Analytics engine ready for UI consumption in Plan 04 (analytics dashboard)
- Endpoints return standard JSON envelope format compatible with existing frontend fetch patterns
- Signal subscriber automatically collects data from all incoming MQTT messages

## Self-Check: PASSED

All files exist, all commits found, all acceptance criteria met.

---
*Phase: 06-analytics-and-observability*
*Completed: 2026-03-24*
