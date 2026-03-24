---
phase: 03-rules-engine
plan: 02
subsystem: rules-engine
tags: [mqtt, automation, blinker, paho-mqtt, MQTTMatcher, rate-limiting, circuit-breaker]

# Dependency graph
requires:
  - phase: 03-01
    provides: "Condition evaluator (evaluate function) and Rule/AlertHistory models"
  - phase: 01-01
    provides: "Event bus (blinker signals) and MQTT client module"
provides:
  - "RuleEngine class with real-time MQTT message evaluation"
  - "Action executor (publish with __source marker, log to AlertHistory, webhook stub)"
  - "Per-rule sliding-window rate limiter and global circuit breaker"
  - "rule_changed signal for hot-reload support"
affects: [03-03, 03-04, 04-alerting]

# Tech tracking
tech-stack:
  added: [paho.mqtt.matcher.MQTTMatcher]
  patterns: [sliding-window-rate-limiter, loop-prevention-marker, atomic-cache-swap]

key-files:
  created:
    - mqttui/rules/engine.py
    - mqttui/rules/actions.py
    - tests/test_rules_engine.py
  modified:
    - mqttui/events.py
    - mqttui/rules/__init__.py

key-decisions:
  - "Used MQTTMatcher from paho-mqtt for topic wildcard matching instead of manual regex"
  - "Sliding-window deque for rate limiting (O(1) amortized) over fixed-bucket counters"
  - "Rate limit timestamps undo on condition-not-matched to avoid false rate limiting"

patterns-established:
  - "Loop prevention: __source: mqttui-automation marker in published payloads"
  - "Atomic cache swap: build new dict/matcher, then assign (no lock needed for single-threaded)"
  - "Engine fixture with disconnect teardown for test isolation"

requirements-completed: [RULE-02, RULE-03, RULE-04, RULE-05]

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 03 Plan 02: Rule Engine Summary

**RuleEngine with MQTTMatcher topic matching, sliding-window rate limiter, global circuit breaker, and action executor (publish/log/webhook)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-24T09:24:40Z
- **Completed:** 2026-03-24T09:28:21Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- RuleEngine evaluates automation rules against live MQTT messages in real-time
- Loop prevention skips messages with __source: mqttui-automation before any rule evaluation
- Per-rule and global circuit breaker rate limiting using sliding-window deque pattern
- Action executor handles publish (with source marker injection), log (AlertHistory persistence), and webhook (stub)
- 11 comprehensive tests covering all safety mechanisms and action types

## Task Commits

Each task was committed atomically:

1. **Task 1: Add rule_changed signal and action executor** - `5300fa7` (feat)
2. **Task 2: TDD RED - failing tests for RuleEngine** - `6da6825` (test)
3. **Task 2: TDD GREEN - RuleEngine implementation** - `ad1f2ac` (feat)

## Files Created/Modified
- `mqttui/rules/engine.py` - RuleEngine class with cache, matcher, rate limiter, event bus integration
- `mqttui/rules/actions.py` - Action executor for publish, log, webhook action types
- `mqttui/events.py` - Added rule_changed signal for hot-reload support
- `mqttui/rules/__init__.py` - Export RuleEngine from package
- `tests/test_rules_engine.py` - 11 tests covering loop prevention, matching, conditions, rate limits, actions, signals

## Decisions Made
- Used MQTTMatcher from paho-mqtt for topic wildcard matching -- leverages MQTT spec-compliant matching already in our dependency tree
- Sliding-window deque for rate limiting -- O(1) amortized, no external dependencies
- Undo rate-limit timestamp when condition evaluates False -- prevents false rate limiting when many messages match topic but not condition

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test isolation for blinker signal handlers**
- **Found during:** Task 2 (TDD GREEN)
- **Issue:** Tests leaked signal handlers across test cases, causing false assertions
- **Fix:** Added engine and fire_log fixtures with proper disconnect teardown
- **Files modified:** tests/test_rules_engine.py
- **Verification:** All 11 tests pass in sequence
- **Committed in:** ad1f2ac (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for test correctness. No scope creep.

## Issues Encountered
None beyond the test isolation issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- RuleEngine is ready for API integration (Plan 03)
- rule_changed signal is ready for hot-reload on CRUD operations
- Action executor is extensible for future action types

---
*Phase: 03-rules-engine*
*Completed: 2026-03-24*
