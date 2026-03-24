---
phase: 07-plugin-architecture
plan: 01
subsystem: plugins
tags: [pluggy, hookspec, entry_points, plugin-registry, sqlalchemy]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Flask app factory, SQLAlchemy sa instance, test fixtures
provides:
  - MQTTUIPlugin hookspec with 3 hooks (on_message, on_connect, on_rule_trigger)
  - PluginConfig SQLAlchemy model for plugin state persistence
  - PluginRegistry with discover/enable/disable/list operations
  - init_plugin_registry() wired into create_app
affects: [07-02-subprocess-isolation, 07-03-management-ui]

# Tech tracking
tech-stack:
  added: [pluggy>=1.5.0]
  patterns: [pluggy hookspec/hookimpl markers, entry_points-based plugin discovery, module-level singleton registry]

key-files:
  created:
    - mqttui/plugins/__init__.py
    - mqttui/plugins/hookspec.py
    - mqttui/plugins/models.py
    - mqttui/plugins/registry.py
    - tests/test_plugin_registry.py
  modified:
    - requirements.txt
    - mqttui/app.py

key-decisions:
  - "Used pluggy hookspec markers instead of ABC for plugin contracts"
  - "Added __future__ annotations for Python 3.9 compat with union type hints"
  - "Plugins start disabled by default (enabled=False) for safety"

patterns-established:
  - "Plugin hooks use pluggy @hookspec/@hookimpl markers, not abstract methods"
  - "Plugin discovery via importlib.metadata entry_points group 'mqttui.plugins'"
  - "Module-level singleton pattern for registry (init_plugin_registry / get_plugin_registry)"

requirements-completed: [PLUG-01, PLUG-02]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 07 Plan 01: Plugin Contract Layer Summary

**Pluggy-based plugin hookspec with 3 hooks, PluginConfig model, and PluginRegistry with entry_points discovery wired into create_app**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T11:07:42Z
- **Completed:** 2026-03-24T11:10:39Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- MQTTUIPlugin hookspec defines on_message, on_connect, on_rule_trigger hooks via pluggy markers
- PluginConfig SQLAlchemy model persists plugin name, entry_point, enabled state, config_json, version, description
- PluginRegistry discovers plugins via importlib.metadata entry_points and manages enable/disable lifecycle
- Plugin registry automatically initializes during create_app startup
- 16 dedicated tests all passing plus 4 existing app factory tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Plugin hookspec, model, and registry (RED)** - `da6e15b` (test)
2. **Task 1: Plugin hookspec, model, and registry (GREEN)** - `9ed057d` (feat)
3. **Task 2: Wire plugin registry into create_app** - `851a738` (feat)

_Note: Task 1 followed TDD with RED/GREEN commits._

## Files Created/Modified
- `mqttui/plugins/__init__.py` - Package init for plugins module
- `mqttui/plugins/hookspec.py` - MQTTUIPlugin class with pluggy hookspec decorators
- `mqttui/plugins/models.py` - PluginConfig SQLAlchemy model
- `mqttui/plugins/registry.py` - PluginRegistry with discover/enable/disable/list
- `requirements.txt` - Added pluggy>=1.5.0
- `mqttui/app.py` - Import PluginConfig for table creation, init_plugin_registry call
- `tests/test_plugin_registry.py` - 16 tests for hookspec, model, and registry

## Decisions Made
- Used pluggy hookspec markers instead of ABC -- pluggy provides the plugin management infrastructure (discovery, ordering, result collection) that ABC cannot
- Added `from __future__ import annotations` for Python 3.9 compatibility with `dict | None` union types
- Plugins start disabled by default for safety -- explicit enable required
- Python 3.9 entry_points() fallback for dict-style return value

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.9 union type syntax**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `dict | None` syntax requires Python 3.10+; project targets 3.9
- **Fix:** Added `from __future__ import annotations` to hookspec.py and registry.py
- **Files modified:** mqttui/plugins/hookspec.py, mqttui/plugins/registry.py
- **Committed in:** 9ed057d

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor syntax fix for Python version compatibility. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plugin contract layer complete, ready for subprocess isolation (Plan 02)
- hookspec defines the stable API contract for plugin authors
- Registry provides the lifecycle management for management UI (Plan 03)

---
*Phase: 07-plugin-architecture*
*Completed: 2026-03-24*
