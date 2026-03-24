---
phase: 07-plugin-architecture
plan: 02
subsystem: plugins
tags: [subprocess, json-protocol, isolation, blinker, signals]

requires:
  - phase: 07-01
    provides: "Plugin registry, hookspecs, PluginConfig model, events.py signals"
provides:
  - "PluginRunner class with subprocess isolation and JSON protocol"
  - "Signal integration: plugins receive MQTT messages and rule fire events"
  - "Action dispatch: publish and log actions from plugin responses"
affects: [07-03-plugin-management-ui]

tech-stack:
  added: [subprocess]
  patterns: [subprocess-isolation, json-stdin-stdout-protocol, empty-env-security]

key-files:
  created:
    - mqttui/plugins/runner.py
    - tests/test_plugin_runner.py
  modified:
    - mqttui/app.py

key-decisions:
  - "Empty env dict passed to subprocess.Popen for plugin security isolation"
  - "JSON protocol: stdin receives {event, data}, stdout returns {actions: [...]}"
  - "5-second timeout with proc.kill() for hung plugins"

patterns-established:
  - "Subprocess isolation pattern: plugins run in separate processes with no app access"
  - "JSON action protocol: plugins return action dicts dispatched by runner"

requirements-completed: [PLUG-03]

duration: 2min
completed: 2026-03-24
---

# Phase 7 Plan 2: Plugin Runner Subprocess Isolation Summary

**Subprocess isolation runner executing plugins in separate processes via JSON stdin/stdout protocol with 5s timeout and blinker signal integration**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T11:12:28Z
- **Completed:** 2026-03-24T11:14:38Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- PluginRunner with subprocess isolation (empty env, no app access)
- JSON protocol: event+data on stdin, actions list on stdout
- Timeout handling kills hung plugins after 5 seconds
- Signal integration: runner receives MQTT messages and rule fire events automatically
- 12 comprehensive tests covering subprocess, timeout, JSON, dispatch

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for PluginRunner** - `e7b35bd` (test)
2. **Task 1 (GREEN): PluginRunner implementation** - `3526bb4` (feat)
3. **Task 2: Wire plugin runner to event bus** - `093425f` (feat)

## Files Created/Modified
- `mqttui/plugins/runner.py` - PluginRunner class with subprocess isolation, JSON protocol, timeout handling, action dispatch
- `tests/test_plugin_runner.py` - 12 tests covering call_plugin, dispatch_message, dispatch_actions, timeout, security
- `mqttui/app.py` - Added init_plugin_runner and signal connections for mqtt_message_received and rule_fired

## Decisions Made
- Empty env dict passed to subprocess.Popen ensures plugins cannot access app environment variables or secrets
- JSON protocol uses newline-delimited format for clean stdin/stdout communication
- 5-second timeout is sufficient for plugin processing while preventing hung processes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plugin runner is complete and wired to the event bus
- Ready for Plan 03: Plugin management UI to enable/disable plugins and view their status

---
*Phase: 07-plugin-architecture*
*Completed: 2026-03-24*

## Self-Check: PASSED
