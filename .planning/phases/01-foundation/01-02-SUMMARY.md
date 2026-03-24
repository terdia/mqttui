---
phase: 01-foundation
plan: 02
subsystem: mqtt
tags: [paho-mqtt, blinker, event-bus, mqtt-v2, signals]

# Dependency graph
requires:
  - phase: 01-foundation-01
    provides: "Flask app factory, extensions, state module, blueprint structure"
provides:
  - "paho-mqtt 2.x client module with CallbackAPIVersion.VERSION2"
  - "Blinker event bus with mqtt_message_received, rule_fired, alert_triggered signals"
  - "Decoupled message flow: broker -> paho -> signal -> (SocketIO + DB)"
  - "Centralized publish function in mqttui.mqtt_client"
affects: [03-rules-engine, 04-alerting, mqtt-client]

# Tech tracking
tech-stack:
  added: [paho-mqtt 2.1.0]
  patterns: [blinker-event-bus, decoupled-message-flow, module-level-signal-handlers]

key-files:
  created: [mqttui/events.py, mqttui/mqtt_client.py]
  modified: [mqttui/app.py, mqttui/routes/main.py, requirements.txt]

key-decisions:
  - "Moved signal handler to module level to avoid blinker weak-reference garbage collection"
  - "All MQTT access centralized through mqttui.mqtt_client module (no direct paho imports elsewhere)"

patterns-established:
  - "Event bus pattern: blinker signals decouple producers from consumers"
  - "Module-level signal handlers: define handlers at module scope for strong references"
  - "Centralized MQTT access: all publish/subscribe through mqtt_client module"

requirements-completed: [FOUND-03, FOUND-06]

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 01 Plan 02: MQTT Client & Event Bus Summary

**paho-mqtt 2.x client with CallbackAPIVersion.VERSION2 and blinker event bus decoupling message flow to SocketIO and database**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T08:30:40Z
- **Completed:** 2026-03-24T08:33:04Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created blinker event bus with three core signals (mqtt_message_received, rule_fired, alert_triggered)
- Migrated MQTT client to paho-mqtt 2.x with correct 5-parameter callback signatures
- Wired message flow through event bus: broker -> paho callback -> blinker signal -> (SocketIO emit + DB persist)
- Centralized all MQTT access through mqttui.mqtt_client module

## Task Commits

Each task was committed atomically:

1. **Task 1: Create blinker event bus and paho-mqtt 2.x client module** - `438c41c` (feat)
2. **Task 2: Wire MQTT client and event bus into app factory** - `ccfe468` (feat)

## Files Created/Modified
- `mqttui/events.py` - Blinker signal definitions (mqtt_message_received, rule_fired, alert_triggered)
- `mqttui/mqtt_client.py` - MQTT client module with paho 2.x CallbackAPIVersion.VERSION2, init_mqtt, publish, get_client
- `mqttui/app.py` - Added init_mqtt call and signal handler wiring in create_app
- `mqttui/routes/main.py` - Updated publish route to use mqtt_client.publish
- `requirements.txt` - Upgraded paho-mqtt from 1.6.1 to 2.1.0

## Decisions Made
- Moved signal handler (_on_mqtt_message) to module level in app.py to avoid blinker weak-reference garbage collection of local function handlers
- All MQTT access goes through mqttui.mqtt_client module -- no direct paho imports in routes or app factory

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed blinker weak-reference garbage collection of signal handler**
- **Found during:** Task 2 (Wire MQTT client and event bus into app factory)
- **Issue:** Signal handler defined as local function inside create_app() was garbage collected after function returned due to blinker's default weak references, resulting in 0 receivers
- **Fix:** Moved _on_mqtt_message handler to module level in mqttui/app.py so it persists as a strong reference
- **Files modified:** mqttui/app.py
- **Verification:** Signal receivers count is 1 after create_app() returns
- **Committed in:** ccfe468 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for signal handler persistence. No scope creep.

## Issues Encountered
- MQTT broker connection refused during verification (expected -- no local broker running). Signal wiring verified independently.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Event bus architecture ready for Phase 3 rules engine to subscribe to mqtt_message_received
- Phase 4 alerting can subscribe to alert_triggered signal
- Publish route centralized through mqtt_client module

---
*Phase: 01-foundation*
*Completed: 2026-03-24*
