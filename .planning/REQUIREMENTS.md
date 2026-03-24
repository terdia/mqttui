# Requirements: MQTTUI v2.0

**Defined:** 2026-03-24
**Core Value:** Users can monitor, interact with, and automate their MQTT infrastructure from a single, intelligent web interface

## v1 Requirements

Requirements for v2.0 release. Each maps to roadmap phases.

### Foundation

- [x] **FOUND-01**: Application uses Flask application factory pattern with blueprints replacing monolithic app.py
- [x] **FOUND-02**: Eventlet replaced with gevent for async mode; Python 3.11+ base image
- [x] **FOUND-03**: paho-mqtt upgraded to 2.x with CallbackAPIVersion.VERSION2 callbacks
- [x] **FOUND-04**: Flask upgraded to 3.1.x with compatible Werkzeug version
- [x] **FOUND-05**: SQLite uses WAL mode with busy_timeout on all connections
- [x] **FOUND-06**: Internal blinker event bus wired (mqtt_message, rule_fired, alert_triggered signals)
- [x] **FOUND-07**: Pytest infrastructure with test fixtures for app factory and MQTT mocking

### REST API

- [x] **API-01**: All existing endpoints formalized under versioned /api/v1/ prefix with OpenAPI documentation
- [x] **API-02**: API responses follow consistent JSON envelope format with status, data, and error fields
- [x] **API-03**: Rate limiting on publish endpoint (configurable per-IP limit)
- [x] **API-04**: CORS support for cross-origin API consumers

### Authentication

- [x] **AUTH-01**: User can log in with username/password and receive session token
- [x] **AUTH-02**: Protected endpoints require valid session token
- [x] **AUTH-03**: User can generate API tokens for programmatic access
- [x] **AUTH-04**: Application refuses to start with default/insecure SECRET_KEY in production mode

### Rules Engine

- [x] **RULE-01**: User can create automation rule with topic pattern trigger and payload condition
- [x] **RULE-02**: User can define rule actions: publish to topic, trigger webhook, or log alert
- [x] **RULE-03**: Rules evaluate against incoming MQTT messages in real-time
- [x] **RULE-04**: Rules engine includes loop detection with per-rule rate limiting and global circuit breaker
- [x] **RULE-05**: User can enable/disable individual rules without deleting them
- [x] **RULE-06**: User can create time-based rules (fire at schedule, e.g., publish heartbeat every 5 minutes)
- [x] **RULE-07**: Rules hot-reload from database without application restart
- [x] **RULE-08**: Rule CRUD available via REST API endpoints

### Alerting

- [x] **ALRT-01**: Rules can fire HTTP webhook to configurable URL with customizable payload template
- [x] **ALRT-02**: Webhook delivery includes retry with exponential backoff on failure
- [ ] **ALRT-03**: Alert deduplication/cooldown prevents alert storms on sustained conditions
- [ ] **ALRT-04**: Alert history persisted and viewable in UI
- [x] **ALRT-05**: Webhook URLs validated against SSRF (block RFC-1918 private addresses)

### Frontend

- [ ] **UI-01**: Frontend refactored from single-file vanilla JS to Alpine.js component architecture
- [ ] **UI-02**: Server-side Socket.IO message batching (100ms window) prevents UI flooding at high throughput
- [ ] **UI-03**: Rules editor UI allows create/edit/delete rules with inline dry-run testing
- [ ] **UI-04**: Alert history viewable in dedicated UI panel
- [ ] **UI-05**: htmx used for non-real-time interactions (forms, CRUD, pagination)
- [ ] **UI-06**: Tailwind CSS v4 via standalone CLI (no Node.js dependency in production)

### Analytics

- [ ] **ANLYT-01**: Per-topic message rate counters displayed in UI
- [ ] **ANLYT-02**: Payload value histograms for numeric payloads
- [ ] **ANLYT-03**: Analytics time-series queries via SQLite JSON1 extension
- [ ] **ANLYT-04**: Structured JSON logging replacing print/stdlib logging (structlog)
- [ ] **ANLYT-05**: Prometheus-compatible /metrics endpoint for production monitoring

### Usability

- [ ] **UX-01**: Topic favorites/bookmarks for quick access to monitored topics
- [ ] **UX-02**: Retained message indicator on messages displayed in UI
- [ ] **UX-03**: Rule dry-run/preview sandbox to test expressions against sample payloads

### Plugin Architecture

- [ ] **PLUG-01**: MQTTUIPlugin abstract base class with defined hook specification
- [ ] **PLUG-02**: Plugin discovery via Python entry_points (importlib.metadata)
- [ ] **PLUG-03**: Plugin execution in subprocess isolation (JSON message in / JSON action out)
- [ ] **PLUG-04**: Plugin management UI (list installed, enable/disable)
- [ ] **PLUG-05**: Bundled example plugins (JSON formatter, topic logger)

## v2 Requirements

Deferred to future releases. Tracked but not in current roadmap.

### Transformation

- **TRANS-01**: Message transformation pipelines using JSONata expressions as rule actions
- **TRANS-02**: Transformation preview showing input/output side-by-side

### Advanced

- **ADV-01**: Multi-broker connection management with broker switching UI
- **ADV-02**: Message replay/time travel from persisted history
- **ADV-03**: Custom dashboard layout with drag-and-drop widget positioning

## Out of Scope

| Feature | Reason |
|---------|--------|
| Visual flow builder (Node-RED style) | Node-RED already does this better; enormous frontend complexity for marginal value |
| Enterprise SSO/SAML/LDAP | Out of scope for self-hosted single-install tool; defer to v3+ |
| Mobile native app | Responsive web covers 80% of mobile use; separate product scope |
| Built-in MQTT broker | Mosquitto/EMQX are mature; recommend docker-compose pairing instead |
| AI/LLM payload analysis | MQTTX Copilot owns this space; doesn't fit control-plane positioning |
| Custom dashboard drag-and-drop | Full layout engine is a product in itself; Grafana exists |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Complete |
| FOUND-02 | Phase 1 | Complete |
| FOUND-03 | Phase 1 | Complete |
| FOUND-04 | Phase 1 | Complete |
| FOUND-05 | Phase 1 | Complete |
| FOUND-06 | Phase 1 | Complete |
| FOUND-07 | Phase 1 | Complete |
| API-01 | Phase 2 | Complete |
| API-02 | Phase 2 | Complete |
| API-03 | Phase 2 | Complete |
| API-04 | Phase 2 | Complete |
| AUTH-01 | Phase 2 | Complete |
| AUTH-02 | Phase 2 | Complete |
| AUTH-03 | Phase 2 | Complete |
| AUTH-04 | Phase 2 | Complete |
| RULE-01 | Phase 3 | Complete |
| RULE-02 | Phase 3 | Complete |
| RULE-03 | Phase 3 | Complete |
| RULE-04 | Phase 3 | Complete |
| RULE-05 | Phase 3 | Complete |
| RULE-06 | Phase 3 | Complete |
| RULE-07 | Phase 3 | Complete |
| RULE-08 | Phase 3 | Complete |
| ALRT-01 | Phase 4 | Complete |
| ALRT-02 | Phase 4 | Complete |
| ALRT-03 | Phase 4 | Pending |
| ALRT-04 | Phase 4 | Pending |
| ALRT-05 | Phase 4 | Complete |
| UI-01 | Phase 5 | Pending |
| UI-02 | Phase 5 | Pending |
| UI-03 | Phase 5 | Pending |
| UI-04 | Phase 5 | Pending |
| UI-05 | Phase 5 | Pending |
| UI-06 | Phase 5 | Pending |
| ANLYT-01 | Phase 6 | Pending |
| ANLYT-02 | Phase 6 | Pending |
| ANLYT-03 | Phase 6 | Pending |
| ANLYT-04 | Phase 6 | Pending |
| ANLYT-05 | Phase 6 | Pending |
| UX-01 | Phase 6 | Pending |
| UX-02 | Phase 6 | Pending |
| UX-03 | Phase 4 | Pending |
| PLUG-01 | Phase 7 | Pending |
| PLUG-02 | Phase 7 | Pending |
| PLUG-03 | Phase 7 | Pending |
| PLUG-04 | Phase 7 | Pending |
| PLUG-05 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 44 total
- Mapped to phases: 44
- Unmapped: 0

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after initial definition*
