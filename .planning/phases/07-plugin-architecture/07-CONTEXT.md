# Phase 7: Plugin Architecture - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the plugin architecture enabling third-party developers to extend MQTTUI with custom handlers. Plugins run in subprocess isolation (JSON in/JSON out), discovered via Python entry_points, managed through a UI. Includes MQTTUIPlugin abstract base class, pluggy hook specification, subprocess isolation boundary, plugin management UI, and bundled example plugins.

</domain>

<decisions>
## Implementation Decisions

### Plugin Hook Specification (pluggy)
- MQTTUIPlugin abstract base class defining hook interface
- Hooks: on_message(topic, payload), on_connect(), on_rule_trigger(rule, result), register_routes(app)
- pluggy hookspec decorators on the base class
- Plugin implementations use pluggy hookimpl decorators

### Plugin Discovery
- Python entry_points via importlib.metadata
- Entry point group: "mqttui.plugins"
- Plugins installed via pip install (standard Python packaging)
- Discovery at startup: scan entry_points, load plugin metadata (name, version, description)

### Subprocess Isolation (Critical Security)
- Plugin code runs in separate subprocess, NOT in-process
- Communication: stdin/stdout JSON protocol
- Plugin subprocess receives: {"event": "on_message", "data": {"topic": "...", "payload": "..."}}
- Plugin subprocess returns: {"actions": [{"type": "publish", "topic": "...", "payload": "..."}]} or {"actions": []}
- Plugin has NO access to: app object, db sessions, mqtt_client, environment variables
- Timeout: 5 seconds per plugin call, kill subprocess if exceeded

### Plugin Management
- PluginConfig SQLAlchemy model (name, entry_point, enabled, config_json, installed_at)
- GET /api/v1/plugins — list installed plugins with status
- POST /api/v1/plugins/<name>/enable — enable plugin
- POST /api/v1/plugins/<name>/disable — disable plugin
- Plugin management UI in dashboard (list, enable/disable toggles)

### Bundled Example Plugins
- JSON Formatter: Formats raw JSON payloads with pretty-printing in the message list
- Topic Logger: Logs all messages on specified topics to a file

### Claude's Discretion
- Exact subprocess communication protocol details (newline-delimited JSON vs length-prefixed)
- Plugin lifecycle management (restart on crash, health checks)
- Whether to use threading.Thread or subprocess.Popen for isolation
- Plugin configuration schema validation
- Example plugin packaging structure

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- mqttui/events.py — blinker signals (mqtt_message_received, rule_fired) for plugin hooks
- mqttui/models.py — SQLAlchemy model patterns for PluginConfig
- mqttui/routes/api_v1.py — API endpoint patterns
- mqttui/app.py — create_app() for wiring plugin registry
- templates/index.html — tab navigation pattern for plugin management UI

### Integration Points
- mqtt_message_received signal — plugin hooks subscribe here
- create_app() — plugin registry initialization
- requirements.txt — pluggy dependency
- templates/index.html — plugins management tab/section

</code_context>

<specifics>
## Specific Ideas

- Research recommended subprocess isolation over in-process for security (CVE-2025-68668)
- Plugin hook API should reflect the stable event bus signals from Phase 1
- Keep plugin API minimal for v1 — expand hooks in future milestones

</specifics>

<deferred>
## Deferred Ideas

- Plugin marketplace/registry — v3+
- Plugin hot-reload without restart — v2.x
- Plugin-to-plugin communication — v3+
- Custom UI widgets from plugins — v3+

</deferred>
