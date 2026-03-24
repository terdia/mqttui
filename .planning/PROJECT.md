# MQTTUI — Next Generation MQTT Web Interface

## What This Is

A real-time web-based MQTT message visualization and control tool that connects to MQTT brokers, displays topic hierarchies as interactive network graphs, persists messages to SQLite, and provides advanced search/filtering. Currently a Python/Flask app (~2,500 lines) with vanilla JS frontend, Socket.IO real-time streaming, and Docker deployment. The goal is to transform it into a powerful, agency-driven MQTT platform with automation capabilities, modern architecture, and a plugin ecosystem.

## Core Value

Users can monitor, interact with, and automate their MQTT infrastructure from a single, intelligent web interface — the app should not just display messages but act on them.

## Requirements

### Validated

- ✓ Real-time MQTT message streaming via Socket.IO — existing
- ✓ Interactive network graph visualization of topic hierarchy (Vis.js) — existing
- ✓ Publish messages to any MQTT topic via web UI — existing
- ✓ SQLite message persistence with configurable limits — existing
- ✓ Advanced search/filtering (topic, content, regex, JSON path, time range) — existing
- ✓ Filter presets (save/load frequently-used filter configs) — existing
- ✓ Debug bar with connection status and performance metrics — existing
- ✓ Docker + Docker Compose deployment with multi-arch support — existing
- ✓ MQTT v3.1.1 and v5 protocol support — existing
- ✓ Configurable via 15+ environment variables — existing
- ✓ Collapsible sidebar with responsive dark theme UI — existing
- ✓ Message rate chart (messages/second via Chart.js) — existing

### Active

- [ ] Automation rules engine — "when topic X receives payload Y, publish to topic Z"
- [ ] Modern, responsive frontend with component-based architecture
- [ ] Plugin/extension architecture for custom handlers
- [ ] Real-time alerting and webhook notifications
- [ ] Enhanced message analytics and dashboards
- [ ] REST API documentation and formalization
- [ ] Testing infrastructure (unit, integration, e2e)
- [ ] Performance and scalability improvements (multi-worker, caching)
- [ ] Message transformation pipelines
- [ ] User authentication and multi-user support
- [ ] Improved error handling and observability (structured logging, metrics export)
- [ ] Topic hierarchy management and favorites

### Out of Scope

- Mobile native app — web-first, responsive design sufficient for v2.0
- Multi-broker management — single broker connection for this milestone
- Enterprise SSO/SAML — basic auth sufficient, enterprise features later
- Message replay/time travel — complex feature, defer to future milestone
- Custom MQTT broker implementation — we connect to existing brokers

## Context

- **Current stack:** Python 3.9+, Flask 2.0.1, Flask-SocketIO, Paho MQTT 1.5.1, SQLite3, vanilla JS, Tailwind CSS, Vis.js, Chart.js
- **Deployment:** Docker + Gunicorn + Eventlet (single worker), Docker Hub at terdia07/mqttui
- **Pain points:** No tests, vanilla JS frontend (~744 lines in one file), hardcoded limits, basic error handling, no exponential backoff, single-worker bottleneck, no structured logging
- **Architecture:** Monolithic Flask app (app.py 524 lines, database.py 461 lines), thread-local SQLite, in-memory message list capped at 100
- **License:** MIT (Terry Osayawe, 2024)
- **Current version:** v1.3.2

## Constraints

- **Tech stack:** Must remain Python backend — too much existing infrastructure to rewrite
- **Backward compatibility:** Existing Docker users must be able to upgrade seamlessly
- **MQTT protocol:** Must support both v3.1.1 and v5
- **Database:** SQLite for single-node; migration path to PostgreSQL is a v2+ concern
- **Performance:** Must handle high-throughput brokers (1000+ msg/sec) without UI lag

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep Python backend | Large existing codebase, Docker users, Flask ecosystem | — Pending |
| Modernize frontend with component framework | Vanilla JS in single file is unmaintainable at scale | — Pending |
| Add automation rules as core differentiator | "Agency" = the app acts autonomously, not just displays | — Pending |
| Plugin architecture for extensibility | Community contributions, custom integrations | — Pending |

---
*Last updated: 2026-03-24 after initialization*
