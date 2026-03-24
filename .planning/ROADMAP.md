# Roadmap: MQTTUI v2.0

## Overview

MQTTUI transforms from a passive MQTT viewer into an active control plane. The v2.0 milestone delivers seven phases: modernizing the architecture (prerequisites first), then adding a versioned REST API with authentication, then the core differentiator (automation rules engine), then webhook alerting, then a modern component-based frontend, then analytics and observability, and finally a plugin architecture — deliberately last so all internal APIs are stable before the plugin contract is published.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Modernize architecture: app factory, gevent, paho-mqtt 2.x, SQLite WAL, blinker event bus, test infrastructure
- [ ] **Phase 2: API and Auth** - Formalize REST API under /api/v1/ with OpenAPI docs and add username/password authentication
- [ ] **Phase 3: Rules Engine** - Build the automation rules engine — IF topic/payload THEN publish/webhook/alert — with loop detection
- [ ] **Phase 4: Alerting** - Deliver webhook notifications with retry, deduplication, SSRF protection, and rule dry-run sandbox
- [ ] **Phase 5: Frontend** - Refactor from single-file vanilla JS to Alpine.js + htmx component architecture with server-side Socket.IO batching
- [ ] **Phase 6: Analytics and Observability** - Per-topic analytics, structured logging, Prometheus metrics, topic favorites, retained message indicator
- [ ] **Phase 7: Plugin Architecture** - Plugin API with subprocess isolation, discovery via entry_points, management UI, and bundled examples

## Phase Details

### Phase 1: Foundation
**Goal**: The application runs on a modern, testable architecture that makes every subsequent phase safe to build
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07
**Success Criteria** (what must be TRUE):
  1. Application starts via `create_app()` factory and all existing features continue to work (real-time streaming, topic graph, publish, search)
  2. Flask server runs under gevent with no eventlet import present anywhere in the codebase
  3. MQTT messages are received and stored correctly after paho-mqtt 2.x callback migration
  4. SQLite database opens with WAL mode and busy_timeout on every connection
  5. `pytest` suite runs with at least app factory and MQTT mock fixtures green
**Plans:** 1/3 plans executed

Plans:
- [ ] 01-01-PLAN.md — App factory, Flask 3.1.x, gevent migration, SQLite WAL
- [ ] 01-02-PLAN.md — paho-mqtt 2.x callback migration, blinker event bus
- [ ] 01-03-PLAN.md — Pytest infrastructure with fixtures and test suite

### Phase 2: API and Auth
**Goal**: Users can securely authenticate and all API consumers have a stable, documented contract
**Depends on**: Phase 1
**Requirements**: API-01, API-02, API-03, API-04, AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. User can log in with username/password and access protected UI and API endpoints
  2. All existing endpoints respond under /api/v1/ prefix with consistent JSON envelope (status, data, error)
  3. OpenAPI documentation is accessible at /api/v1/docs
  4. Requests to the publish endpoint beyond the configured rate limit return 429
  5. Application refuses to start with the default SECRET_KEY when FLASK_ENV=production
**Plans**: TBD

### Phase 3: Rules Engine
**Goal**: Users can automate their MQTT infrastructure — the app acts on messages, not just displays them
**Depends on**: Phase 2
**Requirements**: RULE-01, RULE-02, RULE-03, RULE-04, RULE-05, RULE-06, RULE-07, RULE-08
**Success Criteria** (what must be TRUE):
  1. User can create a rule with a topic pattern and payload condition via REST API, and the rule fires against matching live messages
  2. A rule action can publish to a topic, and the publish is marked with `__source: "mqttui-automation"` so it does not retrigger the rule
  3. A rule exceeding its per-rule rate limit stops firing without crashing the application
  4. User can enable and disable a rule without deleting it, taking effect immediately without restart
  5. User can create a time-based rule that fires on a configurable schedule (e.g., every 5 minutes)
**Plans**: TBD

### Phase 4: Alerting
**Goal**: Rules can notify external systems via webhooks, with reliable delivery and protection against alert storms
**Depends on**: Phase 3
**Requirements**: ALRT-01, ALRT-02, ALRT-03, ALRT-04, ALRT-05, UX-03
**Success Criteria** (what must be TRUE):
  1. A rule with a webhook action delivers an HTTP POST to the configured URL with the expected payload when triggered
  2. A failed webhook delivery is retried with exponential backoff without blocking MQTT message processing
  3. A sustained condition that would generate repeated alerts is deduplicated — only one alert fires during the cooldown window
  4. Alert history is persisted and visible in the UI
  5. A webhook URL pointing to a private RFC-1918 address is rejected with a clear error at rule creation time
**Plans**: TBD

### Phase 5: Frontend
**Goal**: The user interface is maintainable, component-based, and handles high-throughput brokers without flooding the browser
**Depends on**: Phase 4
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06
**Success Criteria** (what must be TRUE):
  1. At 1000+ messages/second, the browser UI remains responsive and does not freeze (server batches Socket.IO emissions into 100ms windows)
  2. User can create, edit, and delete automation rules through the Rules Editor UI without using the raw API
  3. User can run a dry-run test on a rule against a sample payload and see whether the rule would fire
  4. Alert history is visible in a dedicated UI panel
  5. All non-real-time interactions (forms, rule CRUD, pagination) use htmx; no full page reloads required
**Plans**: TBD

### Phase 6: Analytics and Observability
**Goal**: Users and operators can understand what their MQTT infrastructure is doing, both in the UI and in production logs
**Depends on**: Phase 5
**Requirements**: ANLYT-01, ANLYT-02, ANLYT-03, ANLYT-04, ANLYT-05, UX-01, UX-02
**Success Criteria** (what must be TRUE):
  1. Per-topic message rate counters update in real-time in the UI for all active topics
  2. Numeric payload values for a topic are displayed as a histogram showing value distribution
  3. Application logs are structured JSON (structlog) and include request context on every log line
  4. A Prometheus scrape of /metrics returns message rate, active connections, and rule fire counts
  5. User can bookmark a topic as a favorite for quick access, and retained messages are visually distinguished
**Plans**: TBD

### Phase 7: Plugin Architecture
**Goal**: Third-party developers can extend MQTTUI with custom handlers that run in isolation without accessing application internals
**Depends on**: Phase 6
**Requirements**: PLUG-01, PLUG-02, PLUG-03, PLUG-04, PLUG-05
**Success Criteria** (what must be TRUE):
  1. A plugin installed as a Python package is discovered automatically at startup via entry_points without any manual registration
  2. Plugin code runs in a subprocess and can only receive serialized message dicts and return serialized action dicts — it cannot import app, db, or mqtt_client
  3. User can view installed plugins, enable them, and disable them from the plugin management UI
  4. The bundled JSON formatter plugin formats a raw JSON payload into a human-readable string and the result appears in the message list
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 1/3 | In Progress|  |
| 2. API and Auth | 0/? | Not started | - |
| 3. Rules Engine | 0/? | Not started | - |
| 4. Alerting | 0/? | Not started | - |
| 5. Frontend | 0/? | Not started | - |
| 6. Analytics and Observability | 0/? | Not started | - |
| 7. Plugin Architecture | 0/? | Not started | - |
