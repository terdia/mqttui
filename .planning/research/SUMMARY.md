# Project Research Summary

**Project:** mqttui — MQTT Web Interface with Automation
**Domain:** MQTT web interface / IoT dashboard with automation rules engine and plugin architecture
**Researched:** 2026-03-24
**Confidence:** HIGH

## Executive Summary

mqttui is a self-hosted MQTT web interface that already covers the table stakes of a passive MQTT viewer (real-time streaming, topic hierarchy, message history, filtering, publish controls). The v2.0 milestone transforms it into an active control plane: a rules engine that evaluates conditions on incoming messages and fires actions (publish, webhook, alert), a plugin architecture for community extensions, and a modernized stack to support these features without accruing additional technical debt. The research confirms this is achievable as a modular Flask monolith — no microservices, no full rewrite — by incrementally replacing the god-object app.py with blueprints connected via an internal blinker event bus.

The recommended approach is sequenced by hard dependencies: the application factory refactor and eventlet-to-gevent migration must come first (they are prerequisites for every new async feature), followed by the REST API and authentication layer (which gates rules engine UI and the plugin contract), then the rules engine itself (the core differentiator), then webhooks/alerting (rules output), then analytics, then the plugin architecture (deliberately late, after the event bus API stabilizes), and finally the modern component-based frontend. The existing vanilla JS frontend should be refactored using Alpine.js + htmx rather than introducing a full React/Vue build pipeline, keeping the Jinja2 server-rendered model intact.

The primary risks are: (1) rules engine feedback loops where automation publishes trigger themselves — requires loop detection with rate limiting and a circuit breaker at the data model level before any rule can fire a publish; (2) the existing eventlet dependency which is incompatible with Python 3.10+ and causes silent hangs in any new async feature built on top of it — this must be resolved in Phase 1; and (3) SQLite write contention under automation load — requires WAL mode + a single writer queue before the rules engine lands. None of these are blockers — all have clear, documented prevention strategies that must be baked into the relevant phases.

---

## Key Findings

### Recommended Stack

The existing stack needs targeted upgrades, not a replacement. Flask 2.0.1, Werkzeug 2.0.1, paho-mqtt 1.5.1, and eventlet are all multiple major versions behind and must be upgraded before adding new features. The most critical change is dropping eventlet (unmaintained, Python 3.10+ incompatible) in favor of gevent 25.9.1, which also requires bumping the Docker Python base image from 3.9 to 3.11 to meet Gunicorn 25.1.0's Python 3.10+ requirement. The automation rules engine should be built as a custom ECA module (~200-300 lines) backed by APScheduler 3.11.2 for time-based triggers — no external rules library is maintained or appropriate for this use case. Plugin discovery uses pluggy 1.6.0 with Python entry_points. The database layer gains Flask-SQLAlchemy 3.1.1 + Flask-Migrate 4.1.0 for management tables (rules, presets, plugin config) while keeping raw SQLite3 for the high-throughput message insert path.

**Core technologies:**
- Flask 3.1.3 + Werkzeug 3.1.x — framework upgrade, required for Flask-CORS 6.x and modern session semantics
- Flask-SocketIO 5.6.1 + gevent 25.9.1 — replaces eventlet; gevent is the recommended async mode per the author
- paho-mqtt 2.1.0 — breaking API migration from 1.5.1; required before any new MQTT callback work
- APScheduler 3.11.2 — time-based rule triggers; no broker dependency; SQLite job store
- pluggy 1.6.0 + importlib.metadata — plugin discovery via Python entry_points
- Flask-SQLAlchemy 3.1.1 + Flask-Migrate 4.1.0 — ORM for management tables only
- Alpine.js 3.x + htmx 2.0.8 — reactive UI components on top of existing Jinja2 templates; no build pipeline
- Tailwind CSS 4.1.x standalone CLI — no Node.js required in production
- structlog 25.5.0 — structured JSON logging with OpenTelemetry compatibility
- httpx 0.28.1 — outbound webhook delivery with async-friendly timeouts

### Expected Features

The existing product already satisfies all table stakes (real-time streaming, topic tree, subscribe/publish controls, message history, search/filter, connection status, dark mode, Docker). The v2.0 milestone is entirely about differentiators.

**Must have for v2.0 (defines the milestone):**
- Automation Rules Engine (IF topic/payload THEN publish/webhook/alert) — the core differentiator; no competing open-source MQTT web UI does this in-browser
- REST API formalization (OpenAPI-documented versioned routes) — required foundation for rules UI, plugin contract, and external integrations
- User Authentication (basic username/password + session tokens) — any internet-exposed deployment without auth is a security liability
- Real-time Alerting via Webhooks — HTTP POST to configurable URL when a rule fires; closes the monitoring-to-response loop
- Message Transformation Preview / Dry-run — sandbox to test rule expressions before they touch a live broker
- Modern Frontend Component Architecture — refactor 744-line single-file vanilla JS into component-based structure (Alpine.js + htmx on existing Jinja2)

**Should have (v2.x after validation):**
- Message Transformation Pipelines — JSONata expressions as rule actions; add after rules engine is stable
- Per-topic Analytics and Statistics — message rate per topic, value histograms; add when dashboard usage shows demand
- Plugin / Extension Architecture — Python entry-point plugins; add after REST API and event bus API are stable
- Structured Logging and Prometheus Metrics Export — add when operators file issues about production debugging
- Topic Favorites / Bookmarks — low-effort quality-of-life; add any time

**Defer to v3+:**
- Multi-broker Management — data model changes cascade everywhere; significant complexity
- Enterprise SSO/SAML — out of scope for self-hosted single-install tool
- Message Replay / Time Travel — requires ordering guarantees and replay engine
- Visual Flow Builder (Node-RED style) — Node-RED already exists and does this better
- Custom Dashboard Layout (drag-and-drop) — a product in itself; Grafana already exists

### Architecture Approach

The target architecture is a **modular Flask monolith** — the existing app.py god-object is split into bounded modules (blueprints + service classes) that communicate through a blinker internal event bus. MQTT messages arrive via paho-mqtt callback, fire a `mqtt_message` blinker signal, and all consumers (rules engine, analytics aggregator, Socket.IO relay, plugin hooks) independently subscribe without coupling to each other. This preserves the existing Docker deployment and MQTT infrastructure while enabling all new features. The critical path through the architecture is: application factory refactor first (prerequisite for all modules), then event bus + database migrations (shared infrastructure), then rules engine (depends on both), then alerting (depends on rules), then analytics + plugins (depend on event bus), then frontend modernization (depends on stable REST + Socket.IO API surface).

**Major components:**
1. **Application Factory** (`create_app`) — wires blueprints, registers extensions, initializes plugin registry; enables testability
2. **Internal Event Bus** (blinker signals: `mqtt_message`, `rule_fired`, `alert_triggered`) — decouples message receipt from all processing; the true integration point
3. **MQTT Blueprint** — paho-mqtt lifecycle, fires `mqtt_message` on receipt; never imports from rules or analytics
4. **Rules Engine Service** — evaluates stored rules (condition JSON + action JSON in SQLite) against incoming messages; dispatches actions via thread pool
5. **Alert / Webhook Service** — HTTP POST delivery with retry/backoff; subscribes to `rule_fired`; runs in thread pool (never blocks `on_message`)
6. **Plugin Registry** — discovers plugins via `importlib.metadata` entry_points at startup; calls `plugin.setup(signals)`
7. **Analytics Aggregator** — rolling stats subscriber; writes to dedicated SQLite tables
8. **REST API Blueprint** — `/api/*` endpoints; OpenAPI documented; stable contract for frontend and plugins
9. **Frontend** — Alpine.js + htmx on existing Jinja2 templates; throttled Socket.IO message buffering

### Critical Pitfalls

1. **Rules Engine Feedback Loops** — A rule subscribing to a topic that its action publishes to creates a cascade that saturates the broker. Prevention: assign all automation publishes a `__source: "mqttui-automation"` marker and skip rule evaluation for marked messages; enforce a per-rule rate limit (max 10 firings/min); add a global circuit breaker. This must be in the rules data model before any rule can fire a publish — cannot be retrofitted.

2. **Eventlet Deprecation Blocks All New Async Features** — The existing `eventlet==0.30.2` is incompatible with Python 3.10+ and causes silent hangs when combined with `threading.Thread` in new code. Prevention: migrate to `async_mode='gevent'` and `gevent.monkey.patch_all()` in Phase 1, before adding any new async features. This is a cross-cutting change that becomes much harder after rules engine and plugins are layered on top.

3. **SQLite Write Contention Under Automation Load** — Concurrent writers (MQTT ingest + rule action logs + webhook delivery logs) collide without WAL mode and a `busy_timeout`. Prevention: enable `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` on every connection; route all writes through a single writer thread or queue. Must be done before the rules engine phase.

4. **Plugin In-Process Execution Security** — `importlib.import_module()` on user-supplied plugin files gives the plugin full access to app objects, environment variables, and SQLite. Prevention: define a strict subprocess boundary — plugins receive serialized message dicts and return serialized action dicts; no direct access to `mqtt_client`, `db`, or `app`. Design this into the plugin API from day one; retrofitting it is a breaking change.

5. **Real-Time UI Flooding** — `socketio.emit()` called on every MQTT message without batching saturates the browser at >50 msg/sec. Prevention: implement server-side 100ms batch window emitting `mqtt_messages_batch` arrays; add client-side buffer flushed at fixed interval. Must be in place before the modern frontend migration, as component frameworks re-render on every event.

---

## Implications for Roadmap

Based on research, the dependency graph from ARCHITECTURE.md directly maps to a 7-phase structure. The application factory and eventlet migration are strict prerequisites — they cannot be deferred. Every subsequent phase depends on them.

### Phase 1: Foundation — Architecture Modernization and Dependency Upgrade

**Rationale:** The eventlet migration, Flask 3.x upgrade, and application factory refactor are prerequisites for every other phase. Building rules engine or plugin features on top of eventlet creates silent failures and blocks Python 3.10+ compatibility. This phase produces no user-visible features but makes all subsequent phases safe to build.

**Delivers:** Application factory pattern (`create_app`), Flask blueprints replacing god-object app.py, gevent replacing eventlet, paho-mqtt 2.x migration, Flask 3.1.3 + Werkzeug 3.1.x upgrade, SQLite WAL mode + busy_timeout, Python 3.11 base image, blinker event bus wiring, pytest infrastructure.

**Addresses:** Foundation for all FEATURES.md P1 items; none are user-visible yet.

**Avoids:** Eventlet silent hangs blocking async features (Pitfall 2); paho-mqtt callback API failures (Pitfall 6); SQLite write contention groundwork (Pitfall 4).

**Research flag:** Standard patterns — Flask application factory, gevent migration, and paho-mqtt 2.x migration all have well-documented official guides. Skip `/gsd:research-phase`.

---

### Phase 2: REST API Formalization and User Authentication

**Rationale:** The REST API is the stable contract that the rules engine UI, plugin system, and external integrations all depend on. Authentication gates any internet-exposed deployment and must be in place before rules or webhooks are accessible. FEATURES.md dependency graph confirms: Rules Engine requires REST API; Plugin Architecture requires REST API.

**Delivers:** OpenAPI-documented `/api/*` versioned routes, username/password authentication with session tokens, API token support, per-IP rate limiting on publish endpoint, `SECRET_KEY` startup validation (refusing the insecure default).

**Addresses:** REST API formalization (P1), User Authentication (P1).

**Avoids:** Unauthenticated `/publish` endpoint abuse (Security section); `SECRET_KEY` default in production (Security section); Docker upgrade compatibility for new env vars (Pitfall 7).

**Research flag:** Standard patterns — Flask-CORS, JWT sessions, OpenAPI spec generation are well-documented. Skip `/gsd:research-phase`.

---

### Phase 3: Automation Rules Engine

**Rationale:** The core differentiator. This is the reason for the v2.0 milestone. It requires Phase 1 (event bus + WAL mode) and Phase 2 (REST API for rule CRUD) to exist first. The loop detection circuit breaker and per-rule rate limiting must be built into the data model from the start — Pitfall 1 is unfixable by retrofit.

**Delivers:** Rule data model (condition JSON + action JSON stored in SQLite via Flask-SQLAlchemy), condition evaluators (topic pattern match via `paho.mqtt.matcher.MQTTMatcher`, payload contains, JSON path + operator comparison), action handlers (publish with `__source` marker, webhook stub, alert stub), rule CRUD via REST API, hot-reload of active rules, loop detection (rate limit per rule + global circuit breaker), APScheduler time-based triggers.

**Addresses:** Automation Rules Engine (P1 core differentiator).

**Avoids:** Rules feedback loops (Pitfall 1 — must include loop detection in this phase, not later); SQLite write contention (Pitfall 4 — WAL mode from Phase 1 is the prerequisite).

**Research flag:** Needs `/gsd:research-phase` — the condition evaluator DSL (how expressive to make it without going to `eval()`), the JSONata vs simpleeval choice for payload conditions, and the exact rule data model schema would benefit from deeper research before implementation.

---

### Phase 4: Alerting and Webhook Delivery

**Rationale:** Alerting is the output side of the rules engine — it closes the monitoring-to-response loop identified as the most immediate user pain point. Webhooks are rule action types, not a separate subsystem. Building them as Phase 4 (immediately after Phase 3) keeps the surface area small and avoids premature abstraction. Requires Phase 3's rule action dispatch infrastructure.

**Delivers:** HTTP webhook delivery via httpx with retry + exponential backoff, alert deduplication / cooldown (avoid alert storms on sustained conditions), alert history persisted in SQLite, real-time alert notification via Socket.IO, webhook URL SSRF validation (block RFC-1918 addresses), Message Transformation Preview / Dry-run sandbox for testing rule expressions against recent messages.

**Addresses:** Real-time Alerting via Webhooks (P1), Message Transformation Preview (P1).

**Avoids:** Blocking webhook delivery in MQTT callback (Pitfall 5 equivalent — Pitfall architecture anti-pattern 5); webhook SSRF attacks (Security section); alert storm flooding (UX pitfalls).

**Research flag:** Standard patterns — httpx retry, SSRF validation, deduplication cooldown are well-documented. Skip `/gsd:research-phase`.

---

### Phase 5: Modern Frontend Component Architecture

**Rationale:** The rules engine and auth features require UI that cannot be reasonably built on the existing 744-line single-file vanilla JS. The server-side batching for Socket.IO (preventing UI flooding) must be implemented before this phase begins — component frameworks re-render on every event and are far more sensitive than vanilla JS DOM appends. Alpine.js + htmx on existing Jinja2 templates is the correct approach; React/Vue would require a build pipeline and JSON API separation from the template layer.

**Delivers:** Server-side Socket.IO message batching (100ms batch window, `mqtt_messages_batch` event), Alpine.js component structure for dashboard, Rules Editor UI (create/edit/delete rules via REST API), inline rule dry-run testing, alert history UI, structured Tailwind CSS v4 via standalone CLI (no Node.js in production), htmx for all non-real-time interactions (filter forms, rule CRUD, pagination).

**Addresses:** Modern Frontend Architecture (P1), Message Transformation Preview UI (P1).

**Avoids:** Real-time UI flooding (Pitfall 5 — server-side batching must be in place before this phase); SPA catch-all route for Frontend migration (Pitfall checklist item); React/Vue complexity anti-pattern.

**Research flag:** Standard patterns — Alpine.js + htmx + Tailwind v4 standalone CLI on Flask/Jinja2 are well-documented. Skip `/gsd:research-phase`.

---

### Phase 6: Analytics and Observability

**Rationale:** Per-topic analytics depend on the event bus (Phase 1) and the message storage layer, both already stable. Structured logging can ship any time but is grouped here as it addresses the same "operator visibility" need. Plugin architecture is explicitly deferred until Phase 7 to allow the event bus API to fully stabilize — premature plugin hooks cause API churn.

**Delivers:** Per-topic message rate counters, payload value histograms for numeric payloads, analytics time-series queries over SQLite, Analytics Dashboard UI, structlog JSON logging replacing `print()`/stdlib logging, Prometheus-compatible `/metrics` endpoint, Topic Favorites / Bookmarks (low-effort), Retained Message Indicator.

**Addresses:** Per-topic Analytics (P2), Structured Logging / Observability (P2), Topic Favorites / Bookmarks (P2), Retained Message Indicator (P3).

**Avoids:** Python-level JSON path filtering performance trap (load all messages into Python before filtering — use SQLite JSON1 queries instead); `_cleanup_old_messages()` called on every write performance trap (move to background timer).

**Research flag:** May benefit from `/gsd:research-phase` for the analytics query design — SQLite JSON1 extension queries for numeric payload extraction and time-series aggregation have non-obvious performance characteristics.

---

### Phase 7: Plugin Architecture

**Rationale:** Plugin architecture comes last deliberately. The hook API cannot be finalized until the event bus signals, REST API surface, and rules engine action types are proven stable. Premature plugin architecture locks in unstable APIs and erodes contributor trust when hooks change. By Phase 7, all three are stable. The subprocess isolation boundary must be in the design from day one of this phase — it cannot be retrofitted without breaking the plugin API.

**Delivers:** `MQTTUIPlugin` abstract base class, pluggy hook specification (`on_message`, `on_connect`, `on_rule_trigger`, `register_routes`), plugin discovery via `importlib.metadata` entry_points, subprocess isolation for plugin execution (JSON message in / JSON action out), plugin management UI (list, enable/disable), bundled example plugins (JSON formatter, topic logger), plugin configuration storage via Flask-SQLAlchemy.

**Addresses:** Plugin / Extension Architecture (P2).

**Avoids:** Plugin in-process execution security (Pitfall 3 — subprocess boundary is the design, not an afterthought); plugin calling `importlib` to access application internals; plugin path traversal (Security section).

**Research flag:** Needs `/gsd:research-phase` — the pluggy hook specification design, subprocess communication protocol (stdin/stdout JSON vs. named pipes vs. unix sockets), and the plugin packaging contract (`pyproject.toml` entry_points) would benefit from deeper research before API is published.

---

### Phase Ordering Rationale

- **Phase 1 before everything:** eventlet-to-gevent and application factory refactor are cross-cutting; doing them after new features are layered on top multiplies the migration cost.
- **Phase 2 before Phase 3:** REST API is required by rules engine CRUD; auth gates all management endpoints.
- **Phase 3 before Phase 4:** Alerting is a rule action type; building alerting before the rules engine means re-architecting.
- **Phase 3 before Phase 7:** Plugin hook API depends on rules engine action types and event bus signals being stable.
- **Phase 5 after Phase 3:** Rules Editor UI is a core deliverable of the frontend phase; it cannot be built before the rules REST API exists.
- **Server-side batching in Phase 5 before component migration:** Alpine.js components re-render on every Socket.IO event; batching must be server-side before the new templates land.
- **Phase 7 last:** Plugin architecture should not be built until internal APIs are stable — every API change before v2.0 ships breaks plugins built in earlier phases.

### Research Flags

Phases likely needing `/gsd:research-phase` during planning:
- **Phase 3 (Rules Engine):** The condition evaluator DSL design, safe expression evaluation library choice (simpleeval vs. JSONata), exact rule data model schema, and loop detection circuit breaker implementation patterns need deeper research before code is written.
- **Phase 7 (Plugin Architecture):** The pluggy hook specification design, subprocess communication protocol, and `pyproject.toml` entry_points packaging contract should be researched before the plugin API is published — it will be hard to change once plugins exist in the wild.
- **Phase 6 (Analytics):** SQLite JSON1 extension queries for numeric payload extraction and time-series aggregation have non-obvious performance characteristics worth researching before the schema is set.

Phases with standard patterns (skip `/gsd:research-phase`):
- **Phase 1:** Flask application factory, gevent migration, paho-mqtt 2.x migration all have official migration guides.
- **Phase 2:** Flask-CORS, session auth, OpenAPI documentation are well-documented standard patterns.
- **Phase 4:** httpx retry patterns, SSRF validation, deduplication cooldown are standard.
- **Phase 5:** Alpine.js + htmx on Flask/Jinja2 is a documented, well-understood pattern.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified against PyPI; gevent/eventlet recommendation verified against Flask-SocketIO author guidance; paho-mqtt 2.x migration guide is official |
| Features | HIGH | Cross-referenced against MQTTX, ThingsBoard, Node-RED, EMQX, HiveMQ official docs; competitor feature matrix is thorough |
| Architecture | MEDIUM-HIGH | Flask modular monolith and blinker event bus patterns are HIGH confidence from official Flask docs; rules engine specifics are MEDIUM (custom implementation, no reference benchmark) |
| Pitfalls | HIGH | Critical pitfalls verified against official docs, community post-mortems, and CVE data; eventlet deprecation status confirmed from author |

**Overall confidence:** HIGH

### Gaps to Address

- **Rules condition DSL expressiveness:** Research confirmed that no external rules library is appropriate, but the exact boundary of what conditions to support (JSON path operators, regex, arithmetic comparisons, stateful thresholds like "value increasing for 5 consecutive messages") is an open design question. Resolve in Phase 3 planning research.

- **Message Transformation Language:** JSONata is the leading recommendation from FEATURES.md research, but the integration with the rules engine action model and the dry-run sandbox implementation details are not fully specified. Resolve in Phase 3 or Phase 4 planning research.

- **Plugin subprocess communication overhead:** The subprocess isolation model (Pitfall 3 prevention) adds latency vs. in-process hooks. The acceptable latency budget for plugin execution is unknown until the expected plugin use cases are clearer. Resolve in Phase 7 planning research.

- **Gunicorn 25.1.0 requires Python 3.10+, current Dockerfile targets 3.9:** Upgrading to Python 3.11 base image is recommended but requires verifying no existing dependencies break. This is a known gap with a known solution — validate during Phase 1.

- **paho-mqtt 2.x callback migration scope:** The `on_connect`, `on_disconnect`, and `on_message` callback signatures all change with `CallbackAPIVersion.VERSION2`. The full scope of changes in the existing app.py (which handles both MQTTv3 and v5 paths) should be audited before Phase 1 implementation begins.

---

## Sources

### Primary (HIGH confidence)
- Flask PyPI / Flask docs — v3.1.3, application factory pattern, blueprints
- Flask-SocketIO PyPI + deployment docs — v5.6.1, gevent recommendation, eventlet deprecation
- paho-mqtt PyPI + official migration guide — v2.1.0, CallbackAPIVersion breaking changes
- gunicorn PyPI — v25.1.0, Python 3.10+ requirement
- gevent PyPI — v25.9.1
- APScheduler PyPI — v3.11.2 stable, v4.x alpha status confirmed
- pluggy PyPI — v1.6.0
- structlog PyPI — v25.5.0
- Flask-SQLAlchemy / Flask-Migrate PyPI — v3.1.1 / v4.1.0
- Flask-CORS PyPI — v6.0.2
- httpx PyPI — v0.28.1
- Tailwind CSS v4 blog — standalone CLI confirmed, Jan 2025 release
- SQLite WAL mode documentation — concurrent write behavior and busy_timeout
- paho-mqtt 2.0 migration guide (eclipse.dev) — callback API breaking changes
- CVE-2025-68668 — in-process Python sandbox bypass in n8n (plugin security)
- ThingsBoard Rule Engine / EMQX Rule Engine docs — competitor feature reference

### Secondary (MEDIUM confidence)
- EMQ Python MQTT comparison guide — paho-mqtt 2.x recommendation
- APScheduler vs Celery comparison — no-broker advantage for single-node deployment
- Node-RED forum — MQTT automation feedback loop patterns and prevention
- Modular monolith in Python (breadcrumbscollector.tech) — architecture reference
- High-frequency MQTT React dashboard (Medium) — throttled state pattern

### Tertiary (LOW confidence / design inference)
- Custom ECA module approach — no external benchmark; estimated 200-300 lines is a design estimate, not a measured figure
- JSONata as transformation language — strong theoretical fit, not yet validated in Flask context
- Plugin subprocess communication overhead — not benchmarked; acceptable latency budget is assumed based on typical IoT message rates

---
*Research completed: 2026-03-24*
*Ready for roadmap: yes*
