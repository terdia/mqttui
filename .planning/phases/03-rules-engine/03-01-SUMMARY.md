---
phase: 03-rules-engine
plan: 01
subsystem: rules-engine
tags: [sqlalchemy, evaluator, dsl, pytest, apscheduler]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Flask app factory, SQLAlchemy extensions (sa), test fixtures
  - phase: 02-api
    provides: REST API patterns, auth middleware
provides:
  - Rule SQLAlchemy model with 13 columns
  - AlertHistory model for rule firing audit trail
  - Pure-function condition evaluator with 11 operators
  - Compound condition support (all/any combinators)
  - ConditionError exception for malformed conditions
affects: [03-02, 03-03, 03-04]

# Tech tracking
tech-stack:
  added: [APScheduler==3.11.2]
  patterns: [structured JSON DSL for conditions, pure-function evaluator, dot-notation path resolution, numeric string coercion]

key-files:
  created:
    - mqttui/rules/__init__.py
    - mqttui/rules/models.py
    - mqttui/rules/evaluator.py
    - tests/test_rules_evaluator.py
    - tests/test_rules_models.py
  modified:
    - requirements.txt

key-decisions:
  - "Used server_default=sa.func.now() for timestamps to match existing User model pattern"
  - "Evaluator is a pure function with no database or side-effect dependencies"
  - "Numeric coercion applied only to comparison ops (gt, lt, gte, lte) not equality"

patterns-established:
  - "Condition DSL: {path, op, value} with compound {all: [...]} and {any: [...]}"
  - "Rule model stores conditions/actions as JSON text, to_dict() parses them"
  - "Evaluator returns False gracefully for non-dict payloads instead of raising"

requirements-completed: [RULE-01]

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 03 Plan 01: Rules Data Models and Condition Evaluator Summary

**Rule and AlertHistory SQLAlchemy models with pure-function condition evaluator supporting 11 operators, compound conditions, dot-notation paths, and numeric string coercion**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T09:20:29Z
- **Completed:** 2026-03-24T09:22:45Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Rule model with 13 columns covering trigger topics, JSON conditions/actions, rate limits, scheduling, and audit fields
- AlertHistory model for tracking rule firings with severity and timestamps
- Condition evaluator supporting eq, ne, gt, lt, gte, lte, contains, not_contains, regex, exists, not_exists
- 32 total tests (26 evaluator + 6 model) all passing
- APScheduler dependency added for future time-based rule scheduling

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Rule and AlertHistory models and rules package** - `12258fb` (feat)
2. **Task 2: Build pure-function condition evaluator with tests** - `fd026c1` (feat)

_Both tasks followed TDD: RED (failing tests) then GREEN (implementation)_

## Files Created/Modified
- `mqttui/rules/__init__.py` - Package marker for rules engine module
- `mqttui/rules/models.py` - Rule and AlertHistory SQLAlchemy models with to_dict()
- `mqttui/rules/evaluator.py` - Pure-function condition evaluator with 11 operators
- `tests/test_rules_models.py` - 6 unit tests for model columns and to_dict
- `tests/test_rules_evaluator.py` - 26 unit tests covering all operators and edge cases
- `requirements.txt` - Added APScheduler==3.11.2

## Decisions Made
- Used `server_default=sa.func.now()` for created_at/updated_at timestamps, matching existing User model
- Evaluator is a pure function -- no database, no imports from models, no side effects
- Numeric coercion (string->float) applied only to comparison ops, not equality (prevents "5" == 5 being True unexpectedly)
- Empty/None conditions return True (always match) -- design decision for rules with no conditions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Rule and AlertHistory models ready for use in rules CRUD API (plan 03-02)
- Condition evaluator ready for integration with MQTT message pipeline (plan 03-03)
- APScheduler dependency available for time-based rule scheduling (plan 03-04)

---
*Phase: 03-rules-engine*
*Completed: 2026-03-24*
