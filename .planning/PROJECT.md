# MQTTUI — Intelligent MQTT Web Interface

## What This Is

A real-time web-based MQTT automation platform that monitors, visualizes, and acts on MQTT messages. Features an automation rules engine (IF topic/payload THEN publish/webhook/alert), interactive topic hierarchy graph, per-topic analytics, structured logging with Prometheus metrics, and a subprocess-isolated plugin architecture. Built on Python/Flask with Alpine.js + htmx frontend, deployed via Docker.

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
- ✓ Docker + Docker Compose deployment with multi-arch support — existing
- ✓ MQTT v3.1.1 and v5 protocol support — existing
- ✓ Flask application factory with blueprints — v2.0
- ✓ gevent async mode replacing eventlet — v2.0
- ✓ paho-mqtt 2.x with modern callback API — v2.0
- ✓ SQLite WAL mode with busy_timeout — v2.0
- ✓ Blinker event bus (mqtt_message, rule_fired, alert_triggered) — v2.0
- ✓ Pytest infrastructure with 218+ tests — v2.0
- ✓ Versioned REST API at /api/v1/ with OpenAPI docs — v2.0
- ✓ User authentication (Flask-Login, session + API token) — v2.0
- ✓ Rate limiting on publish endpoint — v2.0
- ✓ Automation rules engine with 11-operator condition evaluator — v2.0
- ✓ Loop detection (__source marker + rate limiter + circuit breaker) — v2.0
- ✓ APScheduler time-based rules (cron schedules) — v2.0
- ✓ Webhook delivery with httpx, retry/backoff, SSRF protection — v2.0
- ✓ Alert deduplication/cooldown — v2.0
- ✓ Alpine.js + htmx component-based frontend — v2.0
- ✓ Server-side Socket.IO batching (100ms window) — v2.0
- ✓ Rules Editor UI with inline dry-run testing — v2.0
- ✓ Per-topic analytics with rate counters and histograms — v2.0
- ✓ Structured JSON logging (structlog) — v2.0
- ✓ Prometheus /metrics endpoint — v2.0
- ✓ Topic favorites/bookmarks — v2.0
- ✓ Plugin architecture with subprocess isolation — v2.0

### Active

- [ ] Message transformation pipelines (JSONata expressions)
- [ ] Multi-broker connection management
- [ ] Custom dashboard layout
- [ ] Plugin hot-reload without restart
- [ ] Mobile-optimized responsive breakpoints

### Out of Scope

- Visual flow builder (Node-RED style) — Node-RED already does this better
- Enterprise SSO/SAML — basic auth sufficient for self-hosted tool
- Mobile native app — responsive web covers 80% of use cases
- Built-in MQTT broker — Mosquitto/EMQX are mature
- AI/LLM payload analysis — MQTTX Copilot owns this space

## Context

- **Current stack:** Python 3.11, Flask 3.1.x, Flask-SocketIO + gevent, paho-mqtt 2.1.0, SQLite3 (WAL), Alpine.js 3.x, htmx 2.x, Tailwind CSS v4
- **Deployment:** Docker + Gunicorn + gevent workers, Docker Hub at terdia07/mqttui
- **Architecture:** Modular Flask monolith with blueprints, blinker event bus, subprocess-isolated plugins
- **Tests:** 218+ pytest tests across 7 phases, all passing
- **License:** MIT (Terry Osayawe, 2024)
- **Current version:** v2.0

## Constraints

- **Tech stack:** Python backend — proven in v2.0
- **Backward compatibility:** Docker users can upgrade seamlessly (env vars preserved)
- **MQTT protocol:** Supports both v3.1.1 and v5
- **Database:** SQLite for single-node with WAL mode
- **Performance:** Handles 1000+ msg/sec with Socket.IO batching

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep Python backend | Large existing codebase, Docker users, Flask ecosystem | ✓ Good |
| Alpine.js + htmx (not React/Vue) | Stays on Jinja2, no build pipeline, 29KB total | ✓ Good |
| Custom rules engine (~300 lines) | No maintained MQTT ECA library; simpleeval too permissive | ✓ Good |
| Subprocess plugin isolation | CVE-2025-68668 proved in-process plugins unsafe | ✓ Good |
| gevent replacing eventlet | Eventlet unmaintained, incompatible with Python 3.10+ | ✓ Good |
| Blinker event bus | Decouples MQTT from all consumers; already a Flask dependency | ✓ Good |
| Structured JSON conditions (not eval) | Security — no code execution in condition evaluator | ✓ Good |

---
*Last updated: 2026-03-24 after v2.0 milestone*
