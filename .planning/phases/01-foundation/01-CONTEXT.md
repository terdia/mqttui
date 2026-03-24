# Phase 1: Foundation - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Modernize the application architecture: Flask application factory pattern with blueprints, eventlet→gevent migration, paho-mqtt 2.x upgrade, Flask 3.1.x upgrade, SQLite WAL mode, blinker event bus, and pytest infrastructure. No user-facing features — this phase makes all subsequent phases safe to build.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app.py (524 lines) — monolithic Flask app with MQTT client, API endpoints, WebSocket handlers
- database.py (461 lines) — SQLite message persistence, filtering, presets, cleanup
- debug_bar.py (77 lines) — development debug panel
- templates/index.html — Jinja2 template with Tailwind dark theme
- static/script.js (744 lines) — vanilla JS frontend logic

### Established Patterns
- Flask app with Flask-SocketIO for real-time
- Paho MQTT client with on_connect/on_message/on_disconnect callbacks
- Thread-local SQLite connections
- Environment variable configuration via python-dotenv
- Gunicorn + Eventlet workers for production

### Integration Points
- entrypoint.sh — Docker startup script (must be updated for gevent)
- docker-compose.yml — includes Mosquitto broker
- Dockerfile / Dockerfile.multiarch — multi-arch builds
- requirements.txt — dependency pins
- .env_example — configuration template

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>
