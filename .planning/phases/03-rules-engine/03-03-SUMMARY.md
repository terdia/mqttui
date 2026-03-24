---
phase: 03-rules-engine
plan: 03
subsystem: api
tags: [flask, rest, crud, mqtt-wildcards, dry-run, blinker-signals]

# Dependency graph
requires:
  - phase: 03-01
    provides: Rule model, evaluator, ConditionError
  - phase: 02-01
    provides: Flask-Login auth, User model, api_token
  - phase: 02-02
    provides: api_success/api_error helpers, JSON envelope pattern
provides:
  - Rules CRUD REST API (8 endpoints under /api/v1/rules)
  - rules_bp Flask blueprint
  - Dry-run test endpoint for rule validation
  - MQTT wildcard topic matcher (_topic_matches helper)
affects: [03-04, 04-alerts, 05-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns: [separate blueprint per resource, _get_or_404 helper pattern, custom MQTT topic matcher]

key-files:
  created:
    - mqttui/routes/rules.py
    - tests/test_rules_api.py
  modified:
    - mqttui/app.py

key-decisions:
  - "Implemented custom _topic_matches() for MQTT wildcard matching instead of importing paho MQTTMatcher (avoids paho dependency in route layer)"
  - "Used sa.session.get(Rule, id) instead of deprecated Rule.query.get(id) for SQLAlchemy 2.0 forward compat"

patterns-established:
  - "Resource blueprint pattern: separate blueprint per domain resource with _get_or_404 helper"
  - "Dry-run endpoint pattern: /resource/<id>/test accepts sample data and returns match results without side effects"

requirements-completed: [RULE-01, RULE-05, RULE-08]

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 03 Plan 03: Rules REST API Summary

**Complete CRUD REST API for automation rules with dry-run testing, MQTT wildcard matching, and 20 integration tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-24T09:24:49Z
- **Completed:** 2026-03-24T09:28:51Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- 8 REST endpoints: list, create, get, update, delete, enable, disable, test (dry-run)
- Custom MQTT wildcard topic matcher supporting + and # patterns
- 20 integration tests covering all endpoints, validation, 404s, and auth guards
- Fixed pre-existing table creation bug (Rule model not imported before sa.create_all)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create rules REST API blueprint with all 8 endpoints** - `921fd0e` (feat)
2. **Task 2: Create integration tests for rules REST API** - `a0f658f` (test)

## Files Created/Modified
- `mqttui/routes/rules.py` - Rules CRUD blueprint with 8 endpoints, validation, signals
- `tests/test_rules_api.py` - 20 integration tests for all rules API endpoints
- `mqttui/app.py` - Register rules_bp blueprint, import Rule model for table creation

## Decisions Made
- Used custom `_topic_matches()` instead of paho's MQTTMatcher to avoid coupling route layer to paho internals
- Used `sa.session.get()` instead of deprecated `Rule.query.get()` for SQLAlchemy 2.0 compat

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Rule model not imported before sa.create_all()**
- **Found during:** Task 1 (test execution)
- **Issue:** `sa.create_all()` in app.py only imported User model, not Rule/AlertHistory, so rules table was never created
- **Fix:** Added `from mqttui.rules.models import Rule, AlertHistory` before `sa.create_all()`
- **Files modified:** mqttui/app.py
- **Verification:** All 102 tests pass including previously-failing test_rules_engine tests
- **Committed in:** 921fd0e (Task 1 commit)

**2. [Rule 3 - Blocking] Blueprint registration needed for tests to work**
- **Found during:** Task 1 (setup)
- **Issue:** Plan 03-04 was supposed to register the blueprint, but tests can't run without it
- **Fix:** Added `app.register_blueprint(rules_bp)` in app factory
- **Files modified:** mqttui/app.py
- **Verification:** All rules API tests pass
- **Committed in:** 921fd0e (Task 1 commit)

**3. [Rule 1 - Bug] Deprecated SQLAlchemy Query.get() warning**
- **Found during:** Task 1 (test output)
- **Issue:** `Rule.query.get(rule_id)` triggers LegacyAPIWarning in SQLAlchemy 2.0
- **Fix:** Replaced with `sa.session.get(Rule, rule_id)`
- **Files modified:** mqttui/routes/rules.py
- **Verification:** Tests pass without deprecation warnings
- **Committed in:** 921fd0e (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** All fixes necessary for correctness. Blueprint registration pulled forward from 03-04.

## Issues Encountered
None beyond the auto-fixed deviations.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Rules API complete and tested, ready for frontend integration
- Plan 03-04 (wiring) can skip blueprint registration (already done)
- Dry-run endpoint available for rule testing UI

---
*Phase: 03-rules-engine*
*Completed: 2026-03-24*
