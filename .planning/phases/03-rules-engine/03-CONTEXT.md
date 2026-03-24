# Phase 3: Rules Engine - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the automation rules engine — the core differentiator. Users create rules that evaluate conditions against incoming MQTT messages and fire actions (publish, webhook, log). Includes loop detection, rate limiting, enable/disable, time-based scheduling, hot-reload, and full REST API CRUD. No competing open-source MQTT web UI does this in-browser.

</domain>

<decisions>
## Implementation Decisions

### Condition Evaluator DSL
- Structured JSON conditions, NOT eval/exec (security)
- Supported operators: eq, ne, gt, lt, gte, lte, contains, not_contains, regex, exists, not_exists
- Condition format: {"path": "temperature", "op": "gt", "value": 30}
- Nested JSON path support using dot notation: "sensors.outdoor.temp"
- Compound conditions: {"all": [...conditions]} and {"any": [...conditions]}
- Payload parsed as JSON when possible; raw string comparison as fallback
- Condition evaluator is a pure function: evaluate(condition_dict, payload_dict) -> bool

### Topic Matching
- Use paho.mqtt.matcher (MQTTMatcher) for MQTT wildcard support (+, #)
- Rule trigger_topic supports standard MQTT wildcards: sensors/+/temp, home/#
- Exact match and wildcard match both supported

### Action Types
- **publish**: Publish to a topic with configurable payload, QoS, retain flag. Marked with __source: "mqttui-automation" in payload metadata
- **webhook**: HTTP POST to URL (stub in Phase 3 — full implementation in Phase 4)
- **log**: Log to alert_history table with severity level and message
- Action format: {"type": "publish", "topic": "alerts/temp", "payload": "{\"alert\": true}", "qos": 1, "retain": false}

### Loop Prevention (Critical)
- All automation publishes include __source: "mqttui-automation" marker in message metadata
- Messages with __source marker are SKIPPED during rule evaluation (prevents feedback loops)
- Per-rule rate limit: max 10 firings per minute (configurable per rule, stored in rule model)
- Global circuit breaker: max 100 total rule firings per minute across all rules
- Circuit breaker auto-resets after 60 seconds of no new firings
- Rate limit state tracked in-memory (dict of rule_id -> deque of timestamps)

### Rule Data Model (SQLAlchemy)
- Rule(id, name, description, trigger_topic, condition_json, action_json, enabled, rate_limit_per_min, schedule_cron, last_fired, fire_count, created_at, updated_at)
- condition_json: JSON string of condition dict
- action_json: JSON string of action dict
- enabled: boolean, default True
- rate_limit_per_min: integer, default 10
- schedule_cron: optional cron expression for time-based rules (null = event-driven only)

### Time-Based Scheduling
- APScheduler 3.x with SQLite job store (shared database)
- Cron-style schedule expressions: "*/5 * * * *" for every 5 minutes
- Time-based rules fire actions on schedule regardless of incoming messages
- Schedule changes take effect on next scheduler tick (no restart needed)

### Hot Reload
- Rules loaded from DB into in-memory cache on startup
- Cache invalidated on any rule CRUD operation via REST API
- No application restart required for rule changes
- Signal rule_changed fires on CRUD to notify subscribers

### REST API (under /api/v1/rules)
- GET /api/v1/rules — list all rules
- POST /api/v1/rules — create new rule
- GET /api/v1/rules/<id> — get rule by ID
- PUT /api/v1/rules/<id> — update rule
- DELETE /api/v1/rules/<id> — delete rule
- POST /api/v1/rules/<id>/enable — enable rule
- POST /api/v1/rules/<id>/disable — disable rule
- POST /api/v1/rules/<id>/test — dry-run rule against a sample payload (returns match result + would-fire actions)

### Claude's Discretion
- Exact module file structure within mqttui/ for rules engine
- Error handling strategy for malformed conditions
- Whether to use a separate RuleEngine class or module-level functions
- APScheduler configuration details (misfire grace time, max instances)
- Exact format of __source marker (property vs payload field)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- mqttui/events.py — blinker signals (mqtt_message_received, rule_fired, alert_triggered)
- mqttui/models.py — User model pattern for SQLAlchemy models
- mqttui/extensions.py — shared db, socketio, login_manager, limiter instances
- mqttui/app.py — create_app() factory with blueprint registration pattern
- mqttui/routes/api_v1.py — API v1 blueprint with JSON envelope pattern
- mqttui/helpers.py — api_success/api_error response helpers
- mqttui/mqtt_client.py — paho-mqtt 2.x client with publish function

### Established Patterns
- Blueprint-based route organization
- Flask-SQLAlchemy models with db.session
- JSON envelope responses via helpers.py
- @login_required on protected API endpoints
- Blinker signals for event bus

### Integration Points
- mqtt_message_received signal in events.py — rules engine subscribes here
- rule_fired signal — fires when a rule matches and executes action
- mqtt_client.publish() — used by publish action type
- api_v1 blueprint — rules CRUD endpoints added here or new blueprint
- create_app() — rules engine initialization
- requirements.txt — APScheduler dependency

</code_context>

<specifics>
## Specific Ideas

- Research recommended building custom ECA evaluator (~200-300 lines), not an external rules library
- simpleeval library considered but too permissive for untrusted input; structured JSON operators are safer
- The dry-run/test endpoint is critical for user adoption — users won't trust rules without testing them first

</specifics>

<deferred>
## Deferred Ideas

- Message transformation pipelines (JSONata expressions) — Phase 4+ after rules engine proves stable
- Complex stateful conditions ("value increasing for 5 consecutive messages") — v2.x
- Visual rule builder UI — Phase 5 (frontend) will add form-based rule editor
- Rule templates/presets — quality-of-life, add after core rules ship

</deferred>
