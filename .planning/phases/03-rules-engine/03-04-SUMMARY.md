---
phase: 03-rules-engine
plan: 04
subsystem: rules
tags: [apscheduler, gevent, cron, hot-reload, blinker, signals]

# Dependency graph
requires:
  - phase: 03-02
    provides: "RuleEngine with cache, rate limiter, loop prevention, topic matching"
  - phase: 03-03
    provides: "Rules REST API with rule_changed signal on CRUD"
provides:
  - "APScheduler GeventScheduler integration for time-based rules"
  - "Hot-reload of rule cache via rule_changed signal"
  - "Scheduler job sync on cache reload (add/update/remove)"
  - "RuleEngine fully wired into create_app"
affects: [04-notifications, 05-frontend, 07-plugins]

# Tech tracking
tech-stack:
  added: [APScheduler 3.11.2, tzlocal]
  patterns: [module-level function for pickle-safe scheduler jobs, singleton pattern for engine access]

key-files:
  created: []
  modified:
    - mqttui/rules/engine.py
    - mqttui/app.py
    - tests/test_rules_engine.py

key-decisions:
  - "Pre-mock scheduler in engine fixture to avoid gevent dependency in tests"
  - "Module-level _fire_scheduled_rule with explicit args for APScheduler pickle compatibility"

patterns-established:
  - "Scheduler jobs use module-level functions with explicit args (no lambdas/bound methods)"
  - "Hot-reload via blinker signal -> cache reload -> scheduler sync"

requirements-completed: [RULE-06, RULE-07]

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 03 Plan 04: Scheduler Integration & Hot-Reload Summary

**APScheduler GeventScheduler for cron-based rules with hot-reload via blinker signals and full app factory integration**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-24T09:30:49Z
- **Completed:** 2026-03-24T09:34:23Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- GeventScheduler with SQLAlchemy job store for time-based rule scheduling
- Hot-reload: rule_changed signal triggers cache rebuild and scheduler job sync
- RuleEngine fully integrated into create_app with automatic startup
- 17 engine tests passing (6 new), 108 total project tests green

## Task Commits

Each task was committed atomically:

1. **Task 1: Add APScheduler integration and hot-reload to RuleEngine** - `dd43aa8` (feat)
2. **Task 2: Integrate RuleEngine into create_app and add scheduler/hot-reload tests** - `d26488c` (feat)

## Files Created/Modified
- `mqttui/rules/engine.py` - Added GeventScheduler, sync_scheduled_jobs, fire_scheduled_rule, hot-reload handler, module-level singleton
- `mqttui/app.py` - Added RuleEngine initialization after MQTT init
- `tests/test_rules_engine.py` - Added hot-reload, cron sync, fire_scheduled, and blueprint registration tests

## Decisions Made
- Pre-mock scheduler in engine fixture to avoid real GeventScheduler in tests (prevents gevent greenlet issues)
- Module-level _fire_scheduled_rule function with explicit (app, rule_id) args for APScheduler pickle serialization compatibility
- app.py already had rules blueprint and model imports from prior plan; only RuleEngine init was added

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing APScheduler dependency**
- **Found during:** Task 1 (pre-check)
- **Issue:** APScheduler not installed in environment
- **Fix:** Ran `python3 -m pip install APScheduler`
- **Files modified:** None (pip install only)
- **Verification:** Import succeeds
- **Committed in:** N/A (runtime dependency)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required dependency installation. No scope creep.

## Issues Encountered
None - plan executed as written.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Rules engine fully operational: event-driven + time-based scheduling
- Phase 3 complete: evaluator, engine, REST API, scheduler all integrated
- Ready for Phase 4 (notifications/webhooks) and Phase 5 (frontend rules UI)

---
*Phase: 03-rules-engine*
*Completed: 2026-03-24*
