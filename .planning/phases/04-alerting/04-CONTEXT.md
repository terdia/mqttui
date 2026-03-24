# Phase 4: Alerting - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the full webhook delivery system as a rule action type, replacing the Phase 3 stub. Includes HTTP POST delivery via httpx with retry/exponential backoff, alert deduplication/cooldown, SSRF validation, alert history persistence and UI endpoint, and dry-run preview sandbox for testing rule expressions against recent messages.

</domain>

<decisions>
## Implementation Decisions

### Webhook Delivery
- httpx for outbound HTTP with configurable timeout (10s default)
- Async delivery in thread pool (never blocks MQTT on_message callback)
- Customizable payload template with Jinja2-style variable substitution: {{topic}}, {{payload}}, {{timestamp}}, {{rule_name}}
- Default payload: JSON with topic, payload, rule_name, timestamp, mqttui_source fields

### Retry with Exponential Backoff
- Max 3 retries on failure (HTTP 5xx or connection error)
- Backoff: 1s, 5s, 25s (5^n seconds)
- 4xx errors (client errors) do NOT retry — fail immediately
- Retry runs in background thread, does not block rule evaluation
- Failed deliveries logged to AlertHistory with error details

### Alert Deduplication / Cooldown
- Per-rule cooldown window: configurable (default 5 minutes)
- During cooldown, matching events are counted but NOT re-alerted
- Cooldown tracked in-memory (dict of rule_id -> last_alert_timestamp)
- After cooldown expires, next matching event fires a new alert
- AlertHistory records include suppressed_count for the cooldown window

### SSRF Validation
- Validate webhook URLs at rule creation/update time (not at fire time)
- Block RFC-1918 private addresses: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
- Block localhost: 127.0.0.0/8, ::1
- Block link-local: 169.254.0.0/16
- Return clear error: "Webhook URL points to a private/reserved address"

### Alert History
- AlertHistory model already exists from Phase 3 (rule_id, severity, message, created_at)
- Extend with: webhook_url, http_status, retry_count, error_detail, suppressed_count, cooldown_until
- GET /api/v1/alerts — list alert history with pagination and filtering
- Alert history visible in UI (Phase 5 will add the frontend component)

### Dry-Run Preview
- POST /api/v1/rules/<id>/test already exists from Phase 3
- Extend to show: would-fire result, action preview (webhook payload that would be sent), condition evaluation trace

### Claude's Discretion
- Exact httpx configuration (pool limits, SSL verification options)
- Thread pool size for webhook delivery
- Whether to use a dedicated webhook delivery queue or direct thread spawning
- AlertHistory pagination defaults (page size, sort order)
- Exact Jinja2 template syntax for payload customization

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- mqttui/rules/actions.py — execute_action() with webhook stub ready to replace
- mqttui/rules/models.py — AlertHistory model (needs extension)
- mqttui/rules/engine.py — RuleEngine with rate limiter, already calls execute_action
- mqttui/routes/rules.py — /api/v1/rules/<id>/test endpoint (dry-run, needs extension)
- mqttui/helpers.py — api_success/api_error JSON envelope helpers

### Established Patterns
- Thread pool via concurrent.futures or gevent.pool for async work
- SQLAlchemy models with db.session for persistence
- JSON envelope API responses
- @login_required on protected endpoints

### Integration Points
- mqttui/rules/actions.py execute_action() — replace webhook stub with full implementation
- mqttui/rules/models.py AlertHistory — extend columns
- mqttui/routes/rules.py — extend test endpoint, add /api/v1/alerts
- requirements.txt — add httpx dependency
- alert_triggered blinker signal in events.py — fire on successful webhook delivery

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard webhook delivery patterns

</specifics>

<deferred>
## Deferred Ideas

- Webhook authentication (signing secrets, HMAC) — v2.x
- Multiple webhook URLs per rule — v2.x
- Custom retry policies per webhook — v2.x
- Email alerting — v2.x, requires SMTP configuration

</deferred>
