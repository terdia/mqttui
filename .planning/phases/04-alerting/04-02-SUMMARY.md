---
phase: 04-alerting
plan: 02
subsystem: alerting
tags: [cooldown, deduplication, alerts-api, pagination, action-preview]

# Dependency graph
requires:
  - phase: 04-alerting
    provides: Webhook delivery, AlertHistory model with suppressed_count/cooldown_until columns
provides:
  - Per-rule CooldownTracker for alert deduplication (default 5 min)
  - GET /api/v1/alerts endpoint with pagination and filtering
  - Dry-run action_preview for webhook, publish, and log action types
affects: [05-ui-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [in-memory-cooldown-singleton, pagination-offset-limit, action-preview-dry-run]

key-files:
  created:
    - mqttui/rules/cooldown.py
    - mqttui/routes/alerts.py
  modified:
    - mqttui/rules/actions.py
    - mqttui/routes/rules.py
    - mqttui/app.py
    - tests/test_cooldown.py
    - tests/test_alerts_api.py

key-decisions:
  - "In-memory CooldownTracker singleton with time.monotonic for clock-independent tracking"
  - "Manual offset/limit pagination instead of Flask-SQLAlchemy paginate for simplicity"
  - "action_preview builds rendered payloads using same template logic as actions.py"

patterns-established:
  - "Module-level singleton pattern for cooldown_tracker (same as ThreadPoolExecutor)"
  - "Cooldown check at webhook dispatch boundary before thread pool submission"

requirements-completed: [ALRT-03, ALRT-04, UX-03]

# Metrics
duration: 5min
completed: 2026-03-24
---

# Phase 04 Plan 02: Cooldown, Alerts API, and Action Preview Summary

**Per-rule cooldown deduplication, paginated GET /api/v1/alerts endpoint, and dry-run action_preview for all action types**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-24T09:51:07Z
- **Completed:** 2026-03-24T09:55:40Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- CooldownTracker prevents alert storms with per-rule 5-minute default window, suppressed count tracking
- Webhook delivery checks cooldown before thread pool submission, logs suppressed alerts to AlertHistory
- GET /api/v1/alerts endpoint with page/per_page pagination and optional rule_id/severity filters
- Dry-run test endpoint enhanced with action_preview showing rendered webhook payload, publish topic/payload, or log message
- 17 new tests (8 cooldown + 9 alerts API), full suite 140/140 green

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Cooldown tests** - `a85b176` (test)
2. **Task 1 (GREEN): CooldownTracker + webhook integration** - `2d24f5a` (feat)
3. **Task 2 (RED): Alerts API tests** - `64629ff` (test)
4. **Task 2 (GREEN): Alerts endpoint + action_preview** - `f8a9814` (feat)

_Note: Both tasks used TDD (RED/GREEN commits)_

## Files Created/Modified
- `mqttui/rules/cooldown.py` - CooldownTracker class with per-rule in-memory cooldown and suppressed count
- `mqttui/routes/alerts.py` - alerts_bp blueprint with paginated GET /api/v1/alerts endpoint
- `mqttui/rules/actions.py` - Cooldown check integrated before webhook thread pool submission
- `mqttui/routes/rules.py` - _build_action_preview for webhook, publish, and log action types
- `mqttui/app.py` - Registered alerts_bp blueprint
- `tests/test_cooldown.py` - 8 tests: first alert, blocking, expiry, independence, custom window, suppressed count, integration
- `tests/test_alerts_api.py` - 9 tests: empty list, pagination, rule_id filter, severity filter, auth required, action_preview for 3 types, no preview on mismatch

## Decisions Made
- Used `time.monotonic` for clock-independent cooldown tracking (not affected by system clock changes)
- Manual offset/limit pagination (`query.offset().limit()`) instead of Flask-SQLAlchemy paginate helper for explicit control
- action_preview reuses `_build_webhook_payload` and `_build_default_payload` from actions.py for consistent rendering
- Fixed condition JSON format in test seeds to use `op`/`path` keys matching evaluator API (not `operator`/`field`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed condition JSON format in test seed data**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Test seed used `{"operator": ">", "field": "temp"}` but evaluator expects `{"op": "gt", "path": "temp"}`
- **Fix:** Changed to correct format `{"op": "gt", "path": "temp", "value": 30}`
- **Files modified:** tests/test_alerts_api.py
- **Verification:** All 9 alerts API tests pass
- **Committed in:** f8a9814 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test data)
**Impact on plan:** Minimal -- test data format correction to match existing evaluator API.

## Issues Encountered
None beyond the condition format fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Alert deduplication operational with configurable per-rule cooldown windows
- Alert history API ready for dashboard consumption in Phase 05
- Action preview enables safe rule testing before enabling in production
- All 140 tests passing across entire test suite

## Self-Check: PASSED

All 7 files verified present. All 4 commits verified in history. All acceptance criteria content checks passed.

---
*Phase: 04-alerting*
*Completed: 2026-03-24*
