# Stack Research

**Domain:** MQTT web interface with automation rules engine, plugin architecture, and real-time frontend
**Researched:** 2026-03-24
**Confidence:** MEDIUM-HIGH (versions verified via PyPI; architecture patterns verified via official docs and multiple sources)

---

## Context: What This Upgrades

The existing stack is Python 3.9+, Flask 2.0.1, Flask-SocketIO 5.1.1, Paho MQTT 1.5.1, Werkzeug 2.0.1, Gunicorn + Eventlet (deprecated), vanilla JS, Tailwind CSS, SQLite3. This document covers what to upgrade and what to add — not what exists and works fine.

---

## Recommended Stack

### Core Framework (Upgrade Path)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Flask | 3.1.3 | Web framework, routing, Jinja2 templates | Current stable; v3.x drops Python 3.8, aligns with modern Werkzeug 3.x, required for Flask-CORS 6.x which requires Python 3.9+ |
| Werkzeug | 3.1.x | WSGI utilities (Flask dependency) | Flask 3.1 requires >= 3.1; the existing 2.0.1 pin is two major versions behind |
| Flask-SocketIO | 5.6.1 | Socket.IO real-time events | Latest stable; Eventlet support dropped in favor of gevent — the existing code uses Eventlet which is no longer maintained |
| python-socketio | 5.x | Flask-SocketIO dependency | Keep pinned to what Flask-SocketIO 5.6.1 requires; do not upgrade independently |
| Gunicorn | 25.1.0 | Production WSGI server | Latest; now requires Python 3.10+ and adds beta HTTP/2. Pair with gevent worker class |
| gevent | 25.9.1 | Async concurrency for Gunicorn + Flask-SocketIO | Replaces eventlet; Flask-SocketIO's author now recommends gevent as eventlet is unmaintained. Single worker, thousands of concurrent WebSocket connections |
| gevent-websocket | 0.10.1 | WebSocket support under gevent | Required by Flask-SocketIO when using gevent async mode |

### MQTT Layer (Upgrade Path)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| paho-mqtt | 2.1.0 | MQTT client (v3.1.1 and v5) | 2.x is the recommended version for new work — 1.5.1 is legacy. v2 adds improved error handling, clean session semantics, and proper Python 3 type hints. API has breaking changes from 1.x that must be handled in migration |

### Automation Rules Engine (New)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| APScheduler | 3.11.2 | Cron and interval triggers for rules | No broker dependency (unlike Celery) — appropriate for single-node deployment. Supports SQLite job store for persistence across restarts. v4 is alpha; use 3.11.2 stable |
| Custom ECA module (built-in) | — | Event-Condition-Action rule evaluation | No Python rule engine library (durable-rules, pyKE) is actively maintained or designed for MQTT ECA. Build a thin custom module: store rules in SQLite, evaluate on every message receipt, execute actions via paho-mqtt publish |

**Rationale for custom rules module:** Libraries like `durable-rules` and `pyKE` are either stale or designed for inference engines, not simple "when topic matches, do X" pipelines. The MQTT ECA pattern is simple enough (condition = topic pattern + payload check, action = publish / webhook / log) that 200-300 lines of Python beats a dependency. APScheduler handles time-based triggers; the MQTT message callback handles event triggers.

### Plugin Architecture (New)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pluggy | 1.6.0 | Plugin hook specification and dispatch | The library pytest uses for its own plugin system; actively maintained, well-documented, designed precisely for "define a hook, let plugins implement it" patterns. Lightweight (no broker, no daemon). Stevedore is heavier and OpenStack-focused — overkill for this project |
| Python entry_points (stdlib) | — | Plugin discovery via package metadata | Standard mechanism for finding installed plugins without a registry. Works with pluggy. Users install a plugin package, and the app discovers it at startup via `importlib.metadata` |

### Database (Migration Path)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Flask-SQLAlchemy | 3.1.1 | ORM for rules, presets, and config tables | Needed to move rule definitions, filter presets, and plugin config out of raw SQLite3 calls. v3 aligns with SQLAlchemy 2.0 semantics |
| Flask-Migrate | 4.1.0 | Alembic-powered database migrations | Required once SQLAlchemy models exist — raw SQLite3 code has no migration path. Flask-Migrate 4.1 is compatible with Flask-SQLAlchemy 3.1.1 and SQLAlchemy 2.0 |
| SQLite3 (stdlib) | — | Message storage (keep existing) | Retain the existing raw SQLite3 path for high-throughput message writes (avoid ORM overhead on hot path). Use Flask-SQLAlchemy only for "management" tables (rules, presets, auth, plugin config) |

### Frontend (Modernization — No Full Rewrite)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Tailwind CSS | 4.1.x | Utility-first CSS | v4 (released Jan 2025) has zero-config automatic content detection and a CSS-first config (`@theme`). For Flask/Jinja2, use the standalone CLI binary — not a Node pipeline. 182x faster incremental rebuilds means local dev is not painful |
| Alpine.js | 3.x (latest) | Reactive UI components in HTML | 15KB; adds `x-data`, `x-model`, `x-show`, `x-for` directly to Jinja2 templates. The correct choice for a server-rendered Flask app that needs dropdowns, modals, toggle state, and real-time counters without a full SPA framework. React/Vue would require a build pipeline and break server-rendered templates |
| htmx | 2.0.8 | Partial HTML updates from server | 14KB; replaces custom Socket.IO DOM-patching for non-real-time interactions (filter form submission, rule CRUD, pagination). Complements Socket.IO for true real-time (Socket.IO stays for message streaming; htmx handles everything else). WebSocket extension (2.0.4) available if needed |
| Socket.IO client | 4.x | Real-time MQTT message streaming | Keep existing — it is the right tool for bidirectional push events. Upgrade to match Flask-SocketIO 5.6.1 server version requirements |

**Why not React or Vue:** The app is server-rendered Jinja2. Introducing React requires a build pipeline (Vite/webpack), a JSON API layer, and separating server from client — a full architectural change. Alpine.js + htmx gives 80% of the interactivity with 5% of the complexity increase.

### Alerting and Webhooks (New)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| httpx | 0.28.1 | Outbound webhook HTTP calls | Modern replacement for `requests`; supports both sync and async. The sync API is sufficient here since webhook dispatch runs in a background thread. `requests` would also work but httpx is actively developed with better timeout defaults |
| Flask-CORS | 6.0.2 | Cross-Origin Resource Sharing headers | Needed if REST API is consumed by external dashboards or the plugin ecosystem. Requires Python 3.9+ (matches our upgrade target) |

### Observability (New)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| structlog | 25.5.0 | Structured JSON logging | The production-grade Python logging library. Wraps stdlib logging so third-party libraries still emit through it. Integrates with ELK/Datadog/Prometheus. Preferred over loguru for complex applications because of its processor pipeline (add context, serialize to JSON, route to sinks). Loguru is simpler but lacks first-party OpenTelemetry integration |
| python-dotenv | 1.x | Environment variable loading | Already in use; upgrade from 0.19 to current. No breaking changes |

### Testing Infrastructure (New)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pytest | 8.x (latest) | Test runner | Standard choice; better fixtures and output than unittest |
| pytest-flask | 1.3.0 | Flask app/client fixtures for pytest | Provides `app`, `client`, `live_server` fixtures. Last release (Oct 2023) includes Flask 3.0 compatibility fix |
| pytest-cov | 5.x | Coverage reporting | Standard with pytest projects |
| pytest-mock | 3.x | Mock/patch fixtures | `mocker` fixture is cleaner than `unittest.mock.patch` decorators |

---

## Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.0.1 | `.env` file loading | Already used; upgrade from 0.19 |
| psutil | 6.x | System metrics for debug bar | Already used; upgrade from 5.9 |
| Werkzeug | 3.1.x | WSGI utilities | Installed as Flask dependency; do not pin separately |
| alembic | 1.13.x | Database migration scripts | Installed as Flask-Migrate dependency |
| importlib.metadata | stdlib | Plugin discovery via entry_points | Use in plugin loader for installed packages |

---

## Installation

```bash
# Upgrade core framework
pip install "Flask>=3.1.3" "Flask-SocketIO>=5.6.1" "Werkzeug>=3.1"

# Upgrade MQTT client (has breaking changes from 1.x — read migration guide)
pip install "paho-mqtt>=2.1.0"

# Upgrade production server (drop eventlet, use gevent)
pip install "gunicorn>=25.1.0" "gevent>=25.9.1" gevent-websocket

# Automation rules engine
pip install "APScheduler>=3.11.2,<4.0"

# Plugin architecture
pip install "pluggy>=1.6.0"

# Database migration layer
pip install "Flask-SQLAlchemy>=3.1.1" "Flask-Migrate>=4.1.0"

# Webhooks and API
pip install "httpx>=0.28.1" "Flask-Cors>=6.0.2"

# Structured logging
pip install "structlog>=25.5.0"

# Testing
pip install -D pytest pytest-flask pytest-cov pytest-mock

# Frontend build (Tailwind CSS v4 — standalone CLI, no Node required)
# Download tailwindcss binary from https://github.com/tailwindlabs/tailwindcss/releases
# Add to PATH or scripts/ directory
```

```html
<!-- Alpine.js — add to base template -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

<!-- htmx — add to base template -->
<script src="https://unpkg.com/htmx.org@2.0.8"></script>
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| gevent | eventlet | Never — eventlet is no longer maintained. Migrate away |
| gevent | threading mode (Flask-SocketIO) | Only if third-party libraries are gevent-incompatible. Threading caps at ~hundreds of concurrent WebSocket connections |
| pluggy | stevedore | If you need OpenStack-style extension discovery or have dozens of plugin types with namespace isolation |
| pluggy | Flask blueprints | Blueprints work for routing isolation but provide no hook/dispatch mechanism for plugins that react to MQTT events |
| APScheduler 3 | Celery Beat | Only if you need distributed task execution across multiple machines. Celery requires Redis/RabbitMQ which contradicts the single-node Docker constraint |
| APScheduler 3 | APScheduler 4 | APScheduler 4 is alpha (4.0.0a6 as of Dec 2025); API changed significantly. Use 3.11.2 stable |
| Custom ECA module | durable-rules | durable-rules is stale (last release 2018) and designed for complex stateful CEP, not simple MQTT routing rules |
| Alpine.js + htmx | React | React requires a full build pipeline (Vite) and a JSON API layer, which is a separate project milestone, not an upgrade. Defer React if the project ever becomes a full SPA |
| Alpine.js + htmx | Vue 3 | Same tradeoff as React — adds build complexity with no clear benefit for a server-rendered Jinja2 app |
| structlog | loguru | Loguru is simpler but lacks first-party OpenTelemetry support and processor pipelines. For an app intended to export metrics, structlog's architecture is more forward-compatible |
| Flask-SQLAlchemy | raw SQLite3 (keep) | Keep raw SQLite3 for the high-throughput message insert path. Only introduce Flask-SQLAlchemy for management tables (rules, presets, auth) where query flexibility matters more than insert throughput |
| httpx | requests | Both work; requests is more familiar but httpx is actively developed with better modern defaults (timeout, connection pooling, HTTP/2). Either is defensible |
| paho-mqtt 2.x | aiomqtt | aiomqtt is the cleaner asyncio choice but requires an async framework (asyncio event loop integration). Flask is sync; paho-mqtt 2.x with threads is simpler and avoids an asyncio-vs-threading mismatch |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| eventlet | No longer maintained; Flask-SocketIO author recommends against it as of 2025. The existing `eventlet==0.30.2` is from 2021 | gevent 25.9.1 |
| Flask 2.0.1 (current) | Two major versions behind; missing Werkzeug 3.x compatibility, modern session cookie options, Python 3.9+ requirement alignment | Flask 3.1.3 |
| paho-mqtt 1.5.1 (current) | Legacy API; 2.x has breaking changes but adds better error handling, MQTT v5 improvements, and modern Python typing | paho-mqtt 2.1.0 |
| APScheduler 4.x alpha | API changed significantly from 3.x; not stable as of March 2026 | APScheduler 3.11.2 |
| Celery | Requires Redis or RabbitMQ broker; introduces distributed complexity incompatible with the single-Docker-container deployment model | APScheduler 3.11.2 |
| React / Vue / Angular | Full SPA frameworks require a build pipeline and JSON API separation from the Jinja2 templates — a full architectural rewrite, not a frontend upgrade | Alpine.js + htmx on top of existing Jinja2 |
| Flask-Admin | Heavy dependency for admin UI; the planned REST API with frontend components is a cleaner long-term investment | Build REST endpoints + Alpine.js UI |
| Tailwind CDN in production | Loads all utilities; slow and wasteful. v4 CDN is explicitly "development only" per Tailwind docs | Tailwind CSS v4 standalone CLI binary |
| Werkzeug 2.0.1 (current) | Incompatible with Flask 3.x. Must upgrade | Werkzeug 3.1.x (installed with Flask 3.1.3) |

---

## Stack Patterns by Variant

**For the automation rules engine:**
- Use APScheduler BackgroundScheduler (not BlockingScheduler) so it runs inside the Flask process
- Store rule definitions in SQLite via Flask-SQLAlchemy (Rule model with condition JSON + action JSON)
- Evaluate rules in the paho-mqtt `on_message` callback — check topic match with `paho.mqtt.matcher.MQTTMatcher` then evaluate payload conditions
- Dispatch actions (publish, webhook call, log) in a thread pool to avoid blocking the MQTT callback thread

**For the plugin system:**
- Define a `MQTTUIPlugin` spec class with pluggy hooks: `on_message(topic, payload)`, `on_connect()`, `on_rule_trigger(rule, message)`, `register_routes(app)`
- Plugins declare `entry_points = {"mqttui.plugins": "myplugin = mypackage:MyPlugin"}` in their pyproject.toml
- The app discovers plugins at startup via `importlib.metadata.entry_points(group="mqttui.plugins")`

**For gevent migration from eventlet:**
- Replace `async_mode='eventlet'` → `async_mode='gevent'` in SocketIO init
- Replace `eventlet.monkey_patch()` → `from gevent import monkey; monkey.patch_all()` at top of app.py (before any other imports)
- Gunicorn command: `gunicorn -w 1 -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker app:app`

**For paho-mqtt 1.x → 2.x migration:**
- The `on_connect` callback signature gains a `reason_code` parameter in v2
- `client.connect()` behavior changed; `clean_session` parameter renamed to `clean_start`
- `CallbackAPIVersion` enum must be specified: `mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)`

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Flask 3.1.3 | Werkzeug >= 3.1, Python 3.9+ | Breaks Werkzeug 2.x pinning |
| Flask-SocketIO 5.6.1 | python-socketio 5.x, Flask 3.x | Do not use eventlet; gevent required for production |
| Flask-SQLAlchemy 3.1.1 | SQLAlchemy 2.0, Flask 3.x | Breaks SQLAlchemy 1.x patterns |
| Flask-Migrate 4.1.0 | Flask-SQLAlchemy >= 3.1.1, Alembic 1.13 | 4.0.4+ correctly handles SQLAlchemy 2.0 URLs |
| Flask-CORS 6.0.2 | Python 3.9+, Flask 3.x | Major version bump from 4.x — check for API changes |
| paho-mqtt 2.1.0 | Python 3.7+ | Breaking API changes from 1.x; CallbackAPIVersion must be set |
| gunicorn 25.1.0 | Python 3.10+ | Upgrade may require Python runtime bump from 3.9 to 3.10 |
| APScheduler 3.11.2 | Python 3.8+ | SQLAlchemyJobStore compatible with SQLAlchemy 2.0 |
| gevent 25.9.1 | Python 3.9+ | Requires C extensions; verify Docker base image has build tools |

**Critical compatibility concern — Gunicorn 25.1.0 requires Python 3.10+.** The current Dockerfile targets Python 3.9. The upgrade either requires bumping the Python base image to 3.11 (recommended) or pinning Gunicorn to the last 3.9-compatible version (21.x). Recommend Python 3.11 — it is the most stable LTS-equivalent Python release as of 2026.

---

## Sources

- [Flask PyPI](https://pypi.org/project/Flask/) — version 3.1.3 confirmed (HIGH confidence)
- [Flask-SocketIO PyPI](https://pypi.org/project/Flask-SocketIO/) — version 5.6.1 confirmed (HIGH confidence)
- [paho-mqtt PyPI](https://pypi.org/project/paho-mqtt/) — version 2.1.0 confirmed (HIGH confidence)
- [gunicorn PyPI](https://pypi.org/project/gunicorn/) — version 25.1.0, Python 3.10+ requirement confirmed (HIGH confidence)
- [gevent PyPI](https://pypi.org/project/gevent/) — version 25.9.1 confirmed (HIGH confidence)
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) — version 3.11.2 stable, 4.x still alpha confirmed (HIGH confidence)
- [pluggy PyPI](https://pypi.org/project/pluggy/) — version 1.6.0 confirmed (HIGH confidence)
- [structlog PyPI](https://pypi.org/project/structlog/) — version 25.5.0 confirmed (HIGH confidence)
- [Flask-SQLAlchemy PyPI](https://pypi.org/project/Flask-SQLAlchemy/) — version 3.1.1 confirmed (HIGH confidence)
- [Flask-Migrate PyPI](https://pypi.org/project/Flask-Migrate/) — version 4.1.0 confirmed (HIGH confidence)
- [Flask-CORS PyPI](https://pypi.org/project/flask-cors/) — version 6.0.2 confirmed (HIGH confidence)
- [httpx PyPI](https://pypi.org/project/httpx/) — version 0.28.1 confirmed (HIGH confidence)
- [pytest-flask PyPI](https://pypi.org/project/pytest-flask/) — version 1.3.0 confirmed (HIGH confidence)
- [Tailwind CSS v4 blog](https://tailwindcss.com/blog/tailwindcss-v4) — v4.0 released Jan 2025, v4.1 April 2025, standalone CLI confirmed (HIGH confidence)
- [Flask-SocketIO deployment docs](https://flask-socketio.readthedocs.io/en/latest/deployment.html) — gevent recommended over eventlet confirmed (HIGH confidence)
- [Flask-SocketIO GitHub discussion #1915](https://github.com/miguelgrinberg/Flask-SocketIO/discussions/1915) — eventlet vs gevent author guidance (HIGH confidence)
- [EMQ Python MQTT guide 2025](https://www.emqx.com/en/blog/comparision-of-python-mqtt-client) — paho-mqtt 2.x recommendation confirmed (MEDIUM confidence)
- [APScheduler vs Celery comparison](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat) — no-broker advantage for APScheduler confirmed (MEDIUM confidence)
- [Pluggy documentation](https://medium.com/@garzia.luke/developing-plugin-architecture-with-pluggy-8eb7bdba3303) — hook spec pattern confirmed (MEDIUM confidence)
- [HTMX 2.0 release announcement](https://htmx.org/posts/2024-06-17-htmx-2-0-0-is-released/) — v2.0 confirmed (HIGH confidence)

---

*Stack research for: MQTT web interface with automation rules engine, plugin architecture, and modern frontend*
*Researched: 2026-03-24*
