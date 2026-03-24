---
phase: 07-plugin-architecture
verified: 2026-03-24T12:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
---

# Phase 07: Plugin Architecture Verification Report

**Phase Goal:** Third-party developers can extend MQTTUI with custom handlers that run in isolation without accessing application internals
**Verified:** 2026-03-24T12:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | MQTTUIPlugin abstract base class defines on_message, on_connect, on_rule_trigger hooks | VERIFIED | `mqttui/plugins/hookspec.py` — all 3 methods present with `@hookspec` markers |
| 2 | Plugins installed as Python packages are discovered via importlib.metadata entry_points at startup | VERIFIED | `registry.py` uses `entry_points(group='mqttui.plugins')`; `init_plugin_registry` called in `app.py` |
| 3 | PluginConfig model tracks plugin name, entry_point, enabled state, and config JSON | VERIFIED | `mqttui/plugins/models.py` — all fields present with correct types |
| 4 | Plugin registry loads discovered plugins and provides enable/disable/list operations | VERIFIED | `PluginRegistry` class with `discover`, `enable`, `disable`, `list_plugins`, `get_enabled_plugins` |
| 5 | Plugin code executes in a subprocess, not in the main Flask process | VERIFIED | `runner.py` uses `subprocess.Popen` with `env={}` isolating the plugin process |
| 6 | Plugin subprocess receives JSON dicts on stdin and returns JSON action dicts on stdout | VERIFIED | `call_plugin` builds `json.dumps({"event": ..., "data": ...})` on stdin; parses `{"actions": [...]}` from stdout |
| 7 | Plugin subprocess has no access to app, db, or mqtt_client objects | VERIFIED | `subprocess.Popen(..., env={})` — empty env dict prevents access to any application environment |
| 8 | A plugin that hangs is killed after 5 seconds timeout | VERIFIED | `PLUGIN_TIMEOUT = 5`; `proc.kill()` on `TimeoutExpired`; test `test_timeout_kills_subprocess` passes |
| 9 | Plugin actions returned from subprocess are dispatched (publish, log) | VERIFIED | `dispatch_actions` handles `publish` (calls `mqtt_client.publish`) and `log` (calls `structlog`) |
| 10 | User can view installed plugins with name, version, enabled status in the management UI | VERIFIED | `templates/partials/plugins.html` renders name, version badge, enabled/disabled status per plugin |
| 11 | User can enable and disable a plugin from the management UI | VERIFIED | `plugins.html` has htmx `hx-post` buttons to `/api/v1/plugins/<name>/enable` and `/disable` |
| 12 | GET /api/v1/plugins returns list of installed plugins; enable/disable endpoints toggle state | VERIFIED | `mqttui/routes/plugins.py` — all 3 endpoints implemented and 39 tests pass |

**Score:** 12/12 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mqttui/plugins/__init__.py` | Package init | VERIFIED | Exists |
| `mqttui/plugins/hookspec.py` | MQTTUIPlugin ABC with pluggy hookspec decorators | VERIFIED | `class MQTTUIPlugin` with `@hookspec` on all 3 hooks |
| `mqttui/plugins/models.py` | PluginConfig SQLAlchemy model | VERIFIED | `class PluginConfig(sa.Model)` with all required fields and `to_dict()` |
| `mqttui/plugins/registry.py` | PluginRegistry class with discover/enable/disable/list | VERIFIED | Full implementation; singleton `init_plugin_registry` / `get_plugin_registry` |
| `mqttui/plugins/runner.py` | PluginRunner class with subprocess isolation and JSON protocol | VERIFIED | `class PluginRunner`; `subprocess.Popen` with `env={}`; timeout=5s; action dispatch |
| `mqttui/routes/plugins.py` | Plugin management REST API and partials | VERIFIED | `plugins_bp` with list, enable, disable, and partial routes |
| `mqttui/plugins/examples/json_formatter.py` | JSON formatter example plugin | VERIFIED | Reads JSON stdin; pretty-prints JSON payloads; `on_message` handler present |
| `mqttui/plugins/examples/topic_logger.py` | Topic logger example plugin | VERIFIED | Reads JSON stdin; logs topic/payload to stderr; returns `log` action |
| `templates/partials/plugins.html` | Plugin management UI partial | VERIFIED | Cards with name, version, enabled badge, enable/disable htmx buttons |
| `tests/test_plugin_registry.py` | Tests for plugin discovery and registry | VERIFIED | 16 tests — all pass |
| `tests/test_plugin_runner.py` | Tests for subprocess isolation and JSON protocol | VERIFIED | 12 tests — all pass (includes `test_empty_env_for_security_isolation`) |
| `tests/test_plugins_api.py` | Tests for plugin API endpoints | VERIFIED | 11 tests — all pass (including example plugin subprocess tests) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `mqttui/plugins/registry.py` | `mqttui/plugins/hookspec.py` | imports MQTTUIPlugin | WIRED | `from mqttui.plugins.hookspec import MQTTUIPlugin, PROJECT_NAME` at line 10 |
| `mqttui/plugins/registry.py` | `mqttui/plugins/models.py` | queries PluginConfig | WIRED | `PluginConfig.query.filter_by(...)` used in `discover`, `enable`, `disable`, `list_plugins`, `get_enabled_plugins` |
| `mqttui/plugins/runner.py` | `subprocess.Popen` | spawns plugin process with stdin/stdout pipes | WIRED | `subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, env={})` |
| `mqttui/plugins/runner.py` | `mqttui/plugins/registry.py` | gets enabled plugins | WIRED | `from mqttui.plugins.registry import get_plugin_registry`; called in `dispatch_message` and `on_rule_trigger` |
| `mqttui/app.py` | `mqttui/plugins/runner.py` | connects runner to mqtt_message_received signal | WIRED | `mqtt_message_received.connect(plugin_runner.on_mqtt_message)` at line 187; `rule_fired.connect(plugin_runner.on_rule_trigger)` at line 188 |
| `mqttui/routes/plugins.py` | `mqttui/plugins/registry.py` | calls get_plugin_registry() for CRUD operations | WIRED | `from mqttui.plugins.registry import get_plugin_registry` used in all 4 route handlers |
| `templates/index.html` | `templates/partials/plugins.html` | lazy-loaded via htmx on Plugins tab click | WIRED | `htmx.ajax('GET', '/partials/plugins', {target: '#plugins-panel', ...})` at line 149 |
| `mqttui/app.py` | `mqttui/routes/plugins.py` | blueprint registration | WIRED | `from mqttui.routes.plugins import plugins_bp` + `app.register_blueprint(plugins_bp)` at lines 139/149 |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PLUG-01 | 07-01-PLAN.md | MQTTUIPlugin abstract base class with defined hook specification | SATISFIED | `hookspec.py` — `MQTTUIPlugin` with `@hookspec` on `on_message`, `on_connect`, `on_rule_trigger` |
| PLUG-02 | 07-01-PLAN.md | Plugin discovery via Python entry_points (importlib.metadata) | SATISFIED | `registry.py` `discover()` uses `entry_points(group='mqttui.plugins')`; called in `init_plugin_registry` during `create_app` |
| PLUG-03 | 07-02-PLAN.md | Plugin execution in subprocess isolation (JSON message in / JSON action out) | SATISFIED | `runner.py` `call_plugin` uses `subprocess.Popen` with `env={}`, JSON stdin/stdout, 5s timeout; confirmed by 12 passing tests |
| PLUG-04 | 07-03-PLAN.md | Plugin management UI (list installed, enable/disable) | SATISFIED | `routes/plugins.py` API + `templates/partials/plugins.html` UI with htmx enable/disable toggles; Plugins tab in `index.html` |
| PLUG-05 | 07-03-PLAN.md | Bundled example plugins (JSON formatter, topic logger) | SATISFIED | `examples/json_formatter.py` and `examples/topic_logger.py` both implement the subprocess JSON protocol; verified by subprocess tests |

No orphaned requirements found — all 5 PLUG-* IDs from REQUIREMENTS.md are accounted for.

---

### Anti-Patterns Found

None. The `return []` instances in `runner.py` are proper error-handling paths for timeout, invalid JSON, and unexpected exceptions — not stub implementations.

---

### Human Verification Required

#### 1. Plugins Tab Render in Browser

**Test:** Start the MQTTUI application, navigate to the dashboard, click the "Plugins" tab.
**Expected:** The Plugins panel lazy-loads and displays "No plugins installed" with instructions, or lists any installed plugins with their enabled/disabled status.
**Why human:** Visual rendering, HTMX lazy-load behavior, and panel refresh after enable/disable cannot be verified programmatically.

#### 2. Enable/Disable Toggle UI Flow

**Test:** With at least one plugin registered in the database (e.g., by running the app after installing an example plugin), click "Enable" on a plugin in the Plugins tab.
**Expected:** The button changes to "Disable", the badge turns green, and the panel refreshes without a full page reload.
**Why human:** HTMX partial reload behavior and visual state change after `hx-on::after-request` callback require a browser.

#### 3. End-to-End Plugin Execution via MQTT Message

**Test:** Enable the `topic_logger` example plugin, then publish an MQTT message to the broker. Check application logs.
**Expected:** The runner spawns a subprocess for the plugin, the plugin logs the topic/payload to stderr (captured in app logs), and returns a `log` action that appears in the structlog output.
**Why human:** Requires a live MQTT broker and real subprocess execution; cannot mock the full signal-to-subprocess-to-dispatch chain in a unit test.

---

## Summary

Phase 07 achieved its goal. All three plans executed cleanly and all 39 automated tests pass.

- **Plan 01** delivered the plugin contract layer: `MQTTUIPlugin` hookspec (3 hooks), `PluginConfig` model, and `PluginRegistry` with entry_points discovery — wired into `create_app`.
- **Plan 02** delivered subprocess isolation: `PluginRunner` spawns plugins in separate processes with an empty environment dict (no app access), communicates via newline-delimited JSON, kills hung processes after 5 seconds, and dispatches `publish`/`log` actions. Wired to `mqtt_message_received` and `rule_fired` blinker signals.
- **Plan 03** delivered the user-facing layer: REST API endpoints (`GET /api/v1/plugins`, `POST .../enable`, `POST .../disable`), a Plugins tab in the dashboard with htmx lazy-load, and two bundled example plugins (`json_formatter`, `topic_logger`) that correctly implement the subprocess JSON protocol.

The phase goal is achieved: third-party developers can extend MQTTUI by publishing a Python package with an `mqttui.plugins` entry point, the plugin is discovered automatically at startup, and when enabled its code runs in a subprocess with no access to application internals.

---

_Verified: 2026-03-24T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
