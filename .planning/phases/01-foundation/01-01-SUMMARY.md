---
phase: 01-foundation
plan: 01
subsystem: infra
tags: [flask, gevent, socketio, sqlite, wal, blueprint, factory-pattern]

# Dependency graph
requires: []
provides:
  - "create_app() Flask application factory"
  - "Blueprint-based route organization (main, api, debug)"
  - "SocketIO with gevent async_mode"
  - "SQLite with WAL mode and busy_timeout"
  - "wsgi.py gunicorn entry point"
  - "Docker infrastructure targeting Python 3.11 with GeventWebSocketWorker"
affects: [01-02, 01-03, 02-mqtt-service, 03-automation]

# Tech tracking
tech-stack:
  added: [Flask 3.1.0, Flask-SocketIO 5.5.1, gevent 24.11.1, gevent-websocket 0.10.1, gunicorn 23.0.0, blinker 1.9.0, paho-mqtt 1.6.1, Werkzeug 3.1.3]
  patterns: [application-factory, blueprint-routing, extension-pattern, wal-mode-sqlite]

key-files:
  created:
    - mqttui/__init__.py
    - mqttui/app.py
    - mqttui/extensions.py
    - mqttui/state.py
    - mqttui/database.py
    - mqttui/routes/__init__.py
    - mqttui/routes/main.py
    - mqttui/routes/api.py
    - mqttui/routes/debug.py
    - wsgi.py
  modified:
    - requirements.txt
    - Dockerfile
    - Dockerfile.multiarch
    - entrypoint.sh
    - .env_example

key-decisions:
  - "Used gevent async_mode for SocketIO instead of threading (production-ready, replaces abandoned eventlet)"
  - "Kept debug_bar as root-level module imported lazily in debug blueprint to minimize coupling"
  - "Added mqttui/state.py for shared in-memory state (messages, topics, connection_count) separate from app factory"

patterns-established:
  - "Application factory: create_app(config=None) in mqttui/app.py"
  - "Blueprint registration: each route group in mqttui/routes/{name}.py with bp = Blueprint()"
  - "Extension pattern: shared instances in mqttui/extensions.py, initialized in create_app()"
  - "WAL mode: all SQLite connections get PRAGMA journal_mode=WAL and busy_timeout=5000"

requirements-completed: [FOUND-01, FOUND-02, FOUND-04, FOUND-05]

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 01 Plan 01: App Factory and Gevent Migration Summary

**Flask 3.1 app factory with blueprint routing, gevent SocketIO, and WAL-mode SQLite replacing monolithic eventlet-based app.py**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-24T08:24:04Z
- **Completed:** 2026-03-24T08:28:27Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- Refactored monolithic app.py into mqttui package with create_app() factory pattern
- Split all routes into main, api, and debug blueprints preserving original URL paths
- Migrated from eventlet to gevent with GeventWebSocketWorker for production use
- Enabled SQLite WAL mode with busy_timeout for concurrent access safety
- Upgraded Docker infrastructure from Python 3.9 to 3.11

## Task Commits

Each task was committed atomically:

1. **Task 1: Create mqttui package with app factory, extensions, and blueprints** - `c48b36d` (feat)
2. **Task 2: Update Docker and entrypoint for gevent, verify full startup** - `5799b01` (feat)

## Files Created/Modified
- `mqttui/__init__.py` - Package marker with __version__ = "2.0.0-dev"
- `mqttui/app.py` - create_app() factory with config, logging, SocketIO, DB, blueprints
- `mqttui/extensions.py` - Shared SocketIO and db instances
- `mqttui/state.py` - In-memory shared state (messages, topics, counters)
- `mqttui/database.py` - MessageDatabase with WAL mode and busy_timeout
- `mqttui/routes/__init__.py` - Empty package marker
- `mqttui/routes/main.py` - UI routes blueprint (/, /publish, /stats, /version)
- `mqttui/routes/api.py` - API routes blueprint (/api/messages, /api/topics, etc.)
- `mqttui/routes/debug.py` - Debug bar routes blueprint with before/after request hooks
- `wsgi.py` - Gunicorn entry point using create_app()
- `requirements.txt` - Updated deps: Flask 3.1.0, gevent, removed eventlet
- `Dockerfile` - Python 3.11-slim base
- `Dockerfile.multiarch` - Python 3.11-slim base for multi-arch builds
- `entrypoint.sh` - GeventWebSocketWorker, wsgi:app target
- `.env_example` - Added DB_ENABLED, DB_PATH, DB_MAX_MESSAGES, DB_CLEANUP_DAYS, MQTT_TOPICS, LOG_LEVEL

## Decisions Made
- Used gevent async_mode for SocketIO instead of threading (production-ready, replaces abandoned eventlet)
- Kept debug_bar as root-level module imported lazily in debug blueprint to minimize refactoring scope
- Added mqttui/state.py for shared in-memory state separate from app factory for clean imports

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added mqttui/state.py for shared state**
- **Found during:** Task 1 (blueprint creation)
- **Issue:** Plan suggested state in app.py or a state.py; blueprints need clean imports of shared state without circular dependencies
- **Fix:** Created dedicated mqttui/state.py module with messages, topics, connection_count, active_websockets, error_log
- **Files modified:** mqttui/state.py
- **Verification:** All blueprint routes import from mqttui.state without circular imports
- **Committed in:** c48b36d (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary for clean blueprint imports. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- App factory pattern ready for MQTT service extraction (Plan 02)
- Blueprint structure ready for new route modules
- SocketIO with gevent ready for WebSocket features
- WAL mode database ready for concurrent access patterns
- Original app.py remains untouched for reference during MQTT migration

## Self-Check: PASSED

All 10 created files verified present. Both task commits (c48b36d, 5799b01) verified in git log.

---
*Phase: 01-foundation*
*Completed: 2026-03-24*
