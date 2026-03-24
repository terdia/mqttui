# Architecture Research

**Domain:** MQTT web interface with automation/agency capabilities (Python/Flask)
**Researched:** 2026-03-24
**Confidence:** MEDIUM-HIGH (Flask/Python patterns HIGH; rules engine specifics MEDIUM)

---

## Standard Architecture

### System Overview

The target architecture for this milestone is a **modular Flask monolith** — not microservices, not a full rewrite. The app.py god-object is split into bounded modules that communicate through an internal event bus (blinker signals), while sharing the same Python process. This preserves backward compatibility, Docker deployment, and the existing MQTT infrastructure while enabling the automation, plugin, and analytics features.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (Client)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Dashboard   │  │  Rules UI    │  │  Analytics   │           │
│  │  Component   │  │  Component   │  │  Component   │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         └─────────────────┴─────────────────┘                   │
│                    Socket.IO + REST API                          │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                     Flask Application                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 Application Factory (create_app)          │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────────────┐  │
│  │  MQTT     │ │  Rules    │ │  Plugin   │ │  REST API      │  │
│  │  Blueprint│ │  Blueprint│ │  Registry │ │  Blueprint     │  │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────────────────┘  │
│        │             │             │                             │
│  ┌─────▼─────────────▼─────────────▼──────────────────────┐     │
│  │               Internal Event Bus (blinker)               │     │
│  │   signals: mqtt.message, rule.fired, alert.triggered     │     │
│  └──────────────────────────────────────────────────────────┘    │
│  ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌────────────────┐   │
│  │  Rules    │ │  Alert /  │ │  Transf- │ │   Analytics    │   │
│  │  Engine   │ │  Webhook  │ │  ormation│ │   Aggregator   │   │
│  │  Service  │ │  Service  │ │  Pipeline│ │   Service      │   │
│  └─────┬─────┘ └─────┬─────┘ └─────┬────┘ └───────┬────────┘   │
│        └─────────────┴─────────────┴───────────────┘            │
│                              │                                   │
│  ┌───────────────────────────▼─────────────────────────────┐    │
│  │                    Database Layer                         │    │
│  │   ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │    │
│  │   │  Messages DB │  │  Rules Store │  │  Plugin Cfg │  │    │
│  │   │  (SQLite)    │  │  (SQLite)    │  │  (SQLite)   │  │    │
│  │   └──────────────┘  └──────────────┘  └─────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │ paho-mqtt
┌────────────────────────────▼────────────────────────────────────┐
│                      MQTT Broker                                  │
│                 (Mosquitto / EMQX / any v3.1.1 or v5)            │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| **Application Factory** (`create_app`) | Wires blueprints, registers extensions, creates plugin registry | All blueprints on startup |
| **MQTT Blueprint** | Manages paho-mqtt lifecycle, subscribes to topics, fires `mqtt.message` signal on every message | Internal event bus (emit); REST API (read status) |
| **Internal Event Bus** (blinker) | In-process pub/sub; decouples message receipt from processing | All services subscribe; MQTT Blueprint emits |
| **Rules Engine Service** | Evaluates stored rules against incoming messages; fires actions (publish, webhook, alert) | Subscribes to `mqtt.message`; writes to Rules Store; emits `rule.fired` |
| **Alert / Webhook Service** | Sends HTTP webhooks, future email/SMS notifications on trigger | Subscribes to `rule.fired` and `alert.triggered`; calls external HTTP endpoints |
| **Transformation Pipeline** | Applies message transforms (JSON extract, format conversion, enrichment) before storage/display | Subscribes to `mqtt.message`; emits transformed message downstream |
| **Plugin Registry** | Discovers, loads, and manages plugin lifecycle; provides hook points | Called by Application Factory at startup; plugins subscribe to event bus signals |
| **Analytics Aggregator** | Maintains rolling counters, topic stats, message rate time-series | Subscribes to `mqtt.message`; writes to Analytics tables in SQLite |
| **REST API Blueprint** | Exposes `/api/*` endpoints for messages, rules, topics, plugins, analytics | Reads from all services/database |
| **SocketIO Layer** | Pushes real-time events (new messages, rule fires, alerts) to browser | Subscribes to event bus signals; emits to connected clients |
| **Database Layer** | Single SQLite file, WAL mode, separate logical tables per domain | Read/written by Rules Engine, Analytics, Plugin Registry, Message store |
| **Frontend (Component-based JS)** | Renders dashboard, rules editor, analytics charts | REST API + Socket.IO |

---

## Recommended Project Structure

```
mqttui/
├── app.py                    # Thin entry point: imports create_app, calls connect_mqtt
├── factory.py                # create_app() — application factory
├── extensions.py             # socketio, db singletons (avoids circular imports)
├── signals.py                # blinker Signal definitions (mqtt_message, rule_fired, etc.)
│
├── mqtt/
│   ├── __init__.py           # Blueprint definition
│   ├── client.py             # paho-mqtt lifecycle, on_message -> signals.mqtt_message.send()
│   └── reconnect.py          # Exponential backoff reconnect logic
│
├── rules/
│   ├── __init__.py           # Blueprint + routes for /api/rules
│   ├── engine.py             # RulesEngine class — evaluates conditions, dispatches actions
│   ├── models.py             # Rule dataclass / DB schema
│   ├── conditions.py         # Condition evaluators (topic match, payload match, JSON path)
│   └── actions.py            # Action handlers (publish, webhook, log, alert)
│
├── plugins/
│   ├── __init__.py           # PluginRegistry — load via importlib or stevedore entry points
│   ├── base.py               # MQTTUIPlugin abstract base class
│   └── builtin/              # Bundled example plugins
│       ├── json_formatter.py
│       └── topic_logger.py
│
├── alerts/
│   ├── __init__.py
│   ├── webhook.py            # HTTP webhook delivery with retry
│   └── deduplication.py     # Cooldown / dedup logic to avoid alert storms
│
├── analytics/
│   ├── __init__.py           # Blueprint + routes for /api/analytics
│   ├── aggregator.py         # Rolling stats subscriber
│   └── models.py             # Analytics DB schema
│
├── api/
│   ├── __init__.py           # Blueprint — registers all /api/* sub-blueprints
│   └── auth.py               # Future: token-based auth middleware
│
├── database/
│   ├── __init__.py
│   ├── connection.py         # Single WAL-mode SQLite connection factory
│   ├── messages.py           # MessageDatabase (migrate from database.py)
│   ├── rules.py              # RulesDatabase
│   └── migrations/           # SQL schema migration scripts
│
├── frontend/                 # Component-based JS (Preact recommended — minimal bundle)
│   ├── src/
│   │   ├── components/
│   │   │   ├── MessageFeed.jsx
│   │   │   ├── RulesEditor.jsx
│   │   │   ├── TopicGraph.jsx    # Wraps existing Vis.js logic
│   │   │   └── AnalyticsDash.jsx
│   │   ├── hooks/
│   │   │   ├── useMqttSocket.js  # Socket.IO connection hook
│   │   │   └── useThrottledState.js  # Throttle high-freq updates
│   │   └── main.js
│   ├── package.json
│   └── vite.config.js
│
├── static/                   # Built frontend assets (git-ignored, generated by vite)
├── templates/
│   └── index.html            # Shell template — mounts frontend app
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py           # App factory fixtures
│
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### Structure Rationale

- **factory.py:** The application factory pattern is required for testability. `create_app()` accepts a config object so tests get isolated instances without shared global state.
- **extensions.py:** Defines `socketio = SocketIO()` and `db = ...` without binding them to an app — avoids Flask circular import issues that plague the current `app.py` architecture.
- **signals.py:** Centralizes all blinker signal definitions. Any module can import and subscribe without importing from `mqtt/` directly — keeps the event bus the true integration point.
- **rules/:** Self-contained enough to be tested entirely without an MQTT connection. Engine takes a message dict, returns triggered actions — pure function at its core.
- **plugins/:** Intentionally simple first iteration. Entry-point-based discovery (stevedore/importlib.metadata) is the right pattern but adds packaging complexity; start with importlib direct loading from a configured plugin path.
- **frontend/:** Compiled separately, served as static files. Vite build outputs into `static/`. Flask serves static normally. No Node.js in production Docker image.

---

## Architectural Patterns

### Pattern 1: Internal Event Bus (blinker signals)

**What:** MQTT messages flow through a named blinker signal (`mqtt_message`) rather than being processed directly inside `on_message`. All interested parties (rules engine, analytics, Socket.IO relay, plugins) independently subscribe to that signal.

**When to use:** Any time a single event needs N independent consumers without coupling them together. This is the right pattern when the MQTT Blueprint should not know that a rules engine exists.

**Trade-offs:** Pure in-process; no persistence, no replay, no backpressure. Subscribers run synchronously in the same thread that called `send()`. For high-throughput brokers (1000+ msg/sec) this is acceptable only if subscribers are fast (microseconds) — slow subscribers will block MQTT message receipt.

**Example:**
```python
# signals.py
from blinker import Namespace
_signals = Namespace()
mqtt_message = _signals.signal('mqtt-message')
rule_fired = _signals.signal('rule-fired')
alert_triggered = _signals.signal('alert-triggered')

# mqtt/client.py — fires the signal
from mqttui.signals import mqtt_message
def on_message(client, userdata, msg):
    payload = _decode(msg.payload)
    event = {'topic': msg.topic, 'payload': payload, 'timestamp': datetime.now().isoformat()}
    mqtt_message.send(event)  # all subscribers receive this synchronously

# rules/engine.py — subscribes
from mqttui.signals import mqtt_message
@mqtt_message.connect
def evaluate(event):
    for rule in _active_rules:
        if rule.matches(event):
            rule.execute(event)
```

### Pattern 2: Rules Engine as Condition + Action Pairs

**What:** Rules are stored as JSON in SQLite and loaded at startup (with hot-reload on create/update). Each rule is: `{condition: {topic: "sensors/+", payload_contains: "temperature", json_path: "temp", operator: "gt", value: 30}, action: {type: "publish", topic: "alerts/hot", payload: "{temp}°C"}}`.

**When to use:** This is the right model for an MQTT rules engine. It keeps rules data-driven (editable via UI without code changes), supports export/import, and is easy to test with fixtures.

**Trade-offs:** A custom condition/action evaluator is approximately 150-300 lines of Python — well within "build it" territory. Do not adopt a heavy external rules library (durable_rules, PyKE) for this use case; they add dependency complexity without providing meaningful value over a well-structured custom evaluator. Business-rules library is an option if non-technical rule editing is required.

**Example:**
```python
# rules/conditions.py
def evaluate_condition(condition: dict, message: dict) -> bool:
    topic_ok = mqtt_topic_matches(condition.get('topic', '#'), message['topic'])
    if not topic_ok:
        return False
    if 'json_path' in condition:
        actual = extract_json_path(message['payload'], condition['json_path'])
        return compare(actual, condition['operator'], condition['value'])
    if 'payload_contains' in condition:
        return condition['payload_contains'] in message['payload']
    return True
```

### Pattern 3: Plugin Base Class with Hook Registration

**What:** Plugins extend a `MQTTUIPlugin` abstract base class and declare which signals they subscribe to. The `PluginRegistry` loads plugins from a configured directory (using `importlib.import_module`) and calls `plugin.setup(signal_registry)` during startup.

**When to use:** After the core rules/analytics/alerts features are stable. Building plugin architecture too early causes it to be wrong — the API surface is not yet clear.

**Trade-offs:** Entry-point discovery (stevedore) is the production-grade pattern but requires installable packages. For v2.0, a simpler directory-scan approach (`PLUGIN_PATH=/plugins`) works for Docker users who volume-mount custom plugins.

**Example:**
```python
# plugins/base.py
from abc import ABC, abstractmethod

class MQTTUIPlugin(ABC):
    name: str = "unnamed"
    version: str = "0.1.0"

    @abstractmethod
    def setup(self, signals) -> None:
        """Subscribe to signals, register routes, etc."""
        ...

    def teardown(self) -> None:
        pass

# A plugin implementation
class TemperatureAlerter(MQTTUIPlugin):
    name = "temperature-alerter"
    def setup(self, signals):
        signals.mqtt_message.connect(self._handle)
    def _handle(self, event):
        ...
```

### Pattern 4: Throttled Frontend State for High-Frequency Data

**What:** Socket.IO messages arrive at up to 1000/sec. The frontend must not re-render on every message. Instead, buffer incoming messages in a JS array and flush to component state at a fixed interval (250ms default, configurable).

**When to use:** Any MQTT dashboard. Without this, high-throughput brokers make the UI completely unusable.

**Trade-offs:** Adds perceived latency of up to the flush interval. 250ms is imperceptible for humans.

**Example:**
```javascript
// hooks/useThrottledState.js
export function useThrottledMqttMessages(flushMs = 250) {
  const buffer = useRef([]);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (buffer.current.length > 0) {
        setMessages(prev => [...buffer.current, ...prev].slice(0, 500));
        buffer.current = [];
      }
    }, flushMs);
    return () => clearInterval(interval);
  }, [flushMs]);

  const push = useCallback((msg) => { buffer.current.push(msg); }, []);
  return { messages, push };
}
```

---

## Data Flow

### Inbound MQTT Message Flow

```
MQTT Broker
    |
    | paho-mqtt callback (background thread)
    v
mqtt/client.py :: on_message()
    |
    | blinker signal: mqtt_message.send(event)
    |
    +---> rules/engine.py :: evaluate()
    |         |
    |         +-- condition matches? --> actions.py :: execute()
    |                                        |
    |                                        +--> mqtt_client.publish()  [publish action]
    |                                        +--> alerts/webhook.py      [webhook action]
    |                                        +--> signals.rule_fired.send()
    |
    +---> analytics/aggregator.py :: record()
    |         |
    |         +--> UPDATE analytics tables in SQLite
    |
    +---> database/messages.py :: store_message()
    |         |
    |         +--> INSERT INTO messages (SQLite WAL mode)
    |
    +---> socketio relay :: emit('mqtt_message', event)
              |
              +--> All connected browser clients (Socket.IO)
                       |
                       +--> JS buffer --> throttled state update --> React/Preact re-render
```

### Rule CRUD Flow (User Creates a Rule)

```
Browser (Rules Editor UI)
    |
    | POST /api/rules
    v
api/Blueprint :: create_rule()
    |
    +--> rules/models.py :: validate()
    +--> database/rules.py :: insert_rule()
    +--> rules/engine.py :: reload_rules()   [hot-reload active rules list]
    |
    +--> 201 Created response to browser
```

### Alert / Webhook Delivery Flow

```
rules/engine.py :: rule.execute()
    |
    | blinker signal: alert_triggered.send(alert_event)
    v
alerts/webhook.py :: deliver()
    |
    +--> HTTP POST to configured webhook URL
    |       [with retry: 3 attempts, exponential backoff]
    |
    +--> socketio.emit('alert', alert_event)  [real-time UI notification]
    +--> database :: log_alert()              [persisted alert history]
```

### Plugin Loading Flow (Startup)

```
factory.py :: create_app()
    |
    +--> plugins/registry.py :: PluginRegistry.discover(PLUGIN_PATH)
              |
              +--> importlib.import_module() for each .py in plugin dir
              +--> find subclasses of MQTTUIPlugin
              +--> call plugin.setup(signals)
              +--> register plugin in registry dict
```

---

## Component Boundaries (What Talks to What)

| Boundary | Communication Method | Direction | Notes |
|----------|----------------------|-----------|-------|
| MQTT Client → Services | blinker `mqtt_message` signal | Emit only | MQTT client never imports services |
| Rules Engine → MQTT Client | Direct `mqtt_client.publish()` call | One-way | Publish action only; no subscription back |
| Rules Engine → Alerts | blinker `rule_fired` / `alert_triggered` signal | Emit only | Decoupled — alert service does not know about rules |
| Services → Database | Direct function calls (`db.store_*`) | Read/Write | Thread-local SQLite connection per thread |
| Services → Socket.IO | `socketio.emit()` (global singleton) | Emit only | Works from any thread with threading async mode |
| Plugins → Application | `MQTTUIPlugin.setup(signals)` at startup | Subscribe only | Plugins cannot call back into private service internals |
| Frontend → Backend | REST (`/api/*`) + Socket.IO events | Bidirectional | REST for CRUD; Socket.IO for real-time push |
| Analytics Aggregator → REST API | Shared database tables | Read (API reads what aggregator writes) | Not direct coupling — database is the boundary |

---

## Build Order (Phase Dependencies)

The dependency graph determines what must exist before what can be built:

```
1. Application Factory + Blueprint Refactor
       |
       +-- enables all subsequent modules to be built independently
       |
2a. Internal Event Bus (blinker signals)     2b. Database Migrations (WAL mode, new tables)
       |                                              |
       +----------------------+----------------------+
                              |
              3. Rules Engine (conditions + actions)
                     |
                     +-- requires: event bus (to receive messages)
                     +-- requires: database (to persist rules)
                     |
              4. Alert / Webhook Service
                     |
                     +-- requires: rules engine (source of alerts)
                     |
              5. Transformation Pipeline
                     |
                     +-- requires: event bus (intercept messages pre-storage)
                     |
              6. Analytics Aggregator
                     |
                     +-- requires: event bus + database migrations
                     |
              7. Plugin Architecture
                     |
                     +-- requires: application factory + event bus (plugin hooks)
                     +-- should come AFTER core features stabilize the API surface
                     |
8a. Modern Frontend (component JS)           8b. REST API Formalization
       |                                              |
       +-- requires: stable REST + Socket.IO API from all services above
```

**Critical path:** Application Factory refactor (step 1) is the prerequisite for everything. Build that first, get tests green, then proceed in order. Plugin architecture (step 7) deliberately comes late — the hook API cannot be finalized until the event bus and rules engine are stable.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 concurrent users, <100 msg/sec | Current monolith is fine; WAL mode SQLite handles this trivially |
| 10-50 concurrent users, 100-1000 msg/sec | Enable WAL mode + WAL checkpoint tuning; throttle Socket.IO broadcasts (batch emit every 100ms); keep single Gunicorn worker |
| 50+ concurrent users or >1000 msg/sec | SQLite write bottleneck appears; consider SQLite → PostgreSQL migration; multi-worker Gunicorn requires Redis message queue for Socket.IO coordination |
| >5000 msg/sec | Rules engine synchronous evaluation becomes a bottleneck; move rule execution to a thread pool; consider a background task queue (Celery + Redis) for slow actions (webhooks) |

### First Bottleneck

**Single-writer SQLite at high message rates.** At 1000 msg/sec, every message tries to INSERT into SQLite in the callback thread. Mitigation: batch inserts every 500ms using a write buffer. This is a known pattern and straightforward to implement before a DB migration is needed.

### Second Bottleneck

**Synchronous blinker signal dispatch blocking MQTT callback thread.** If any subscriber (rules engine evaluating a complex rule, webhook delivery) takes >10ms, the MQTT network buffer backs up. Mitigation: webhook/alert delivery must be async (thread pool executor or background queue). Rules evaluation should complete in <1ms for typical rule sets.

---

## Anti-Patterns

### Anti-Pattern 1: Importing Services Directly Into `on_message`

**What people do:** Add `from rules_engine import evaluate` directly in `on_message()` inside app.py, then add analytics, then add alerting — the god-object grows back.

**Why it's wrong:** Every new capability re-couples to the message callback. Tests become impossible without a live MQTT broker. The existing app.py is already at this stage.

**Do this instead:** Fire `mqtt_message.send(event)` in `on_message`. All other logic subscribes independently. The MQTT client module never imports from rules, analytics, or alerts.

### Anti-Pattern 2: One SQLite Connection Shared Across Threads

**What people do:** `db = sqlite3.connect('mqtt.db')` at module level, used from Flask request threads, MQTT callback thread, and background workers simultaneously.

**Why it's wrong:** SQLite connections are not thread-safe by default. Results in "database is locked" errors under concurrent load. The current `database.py` uses `check_same_thread=False` which masks this problem rather than solving it.

**Do this instead:** Use `threading.local()` for per-thread connections, or use a single dedicated writer thread with a queue, or enable WAL mode with `PRAGMA journal_mode=WAL` and use separate connection objects per thread. WAL mode allows concurrent readers with a single writer.

### Anti-Pattern 3: Building the Plugin API Before Core Features Are Stable

**What people do:** Design a plugin system upfront so everything is extensible from day one.

**Why it's wrong:** The plugin hook points reflect the internal architecture. If the rules engine, event bus, and analytics service change during development (and they will), every plugin breaks. Plugin API churn erodes contributor trust.

**Do this instead:** Build and stabilize the rules engine and event bus first. The plugin API is a thin wrapper exposing already-stable signals. Define it once, after the signals are proven.

### Anti-Pattern 4: Sending Every MQTT Message Individually to the Browser

**What people do:** `socketio.emit('mqtt_message', message)` inside `on_message` with no throttling.

**Why it's wrong:** At 500 msg/sec, Socket.IO serializes 500 JSON payloads per second and the browser receives 500 events per second, triggering 500 re-renders. The UI becomes unresponsive and memory climbs.

**Do this instead:** Buffer messages server-side for 100ms and batch-emit. Or buffer client-side in a JS `useRef` and flush to React state on a fixed interval. The client-side approach is simpler and reduces network traffic.

### Anti-Pattern 5: Blocking Webhook Delivery in the Signal Handler

**What people do:** Make the HTTP request inside the blinker subscriber that fires on every rule match.

**Why it's wrong:** HTTP calls take 100ms-5s. This blocks the MQTT callback thread for every rule match that triggers a webhook, directly delaying message receipt.

**Do this instead:** Submit webhook tasks to a `concurrent.futures.ThreadPoolExecutor` (already in Python stdlib, no Redis required for v1). The signal handler returns immediately; the executor delivers asynchronously.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| MQTT Broker | paho-mqtt TCP; `loop_start()` background thread | Already implemented; needs exponential backoff on reconnect |
| Webhook endpoints | HTTP POST via `requests` library in thread pool | Configurable per rule; needs timeout + retry with backoff |
| Future: Postgres | SQLAlchemy swap (same models, different engine) | Schema migrations via Alembic when SQLite becomes a bottleneck |
| Future: Redis | Required only if multi-worker Gunicorn is needed for Socket.IO | Not needed until multi-user scale |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| MQTT Client ↔ Rules Engine | blinker signal (no direct import) | Enforced: rules engine is not imported by mqtt module |
| Rules Engine ↔ Database | Direct call to `database/rules.py` functions | Rules module owns its DB schema and queries |
| All Services ↔ Socket.IO | `socketio.emit()` via singleton from `extensions.py` | Threading async mode allows this from any thread safely |
| Plugin ↔ Application | `MQTTUIPlugin.setup(signals)` only | Plugins cannot call internal service methods directly; only subscribe to signals and call public API |
| Frontend ↔ Backend | `/api/*` REST + Socket.IO `mqtt_message` / `rule_fired` / `alert_triggered` events | API contract must be stable before frontend component work begins |

---

## Sources

- Flask Application Factory pattern: https://flask.palletsprojects.com/en/stable/patterns/appfactories/
- Flask Blueprints documentation: https://flask.palletsprojects.com/en/stable/blueprints/
- Blinker signals in Flask: https://flask.palletsprojects.com/en/stable/signals/ + https://github.com/pallets-eco/blinker
- Flask-SocketIO multi-worker limitations: https://flask-socketio.readthedocs.io/en/latest/deployment.html
- Stevedore plugin discovery: https://docs.openstack.org/stevedore/latest/user/tutorial/creating_plugins.html
- SQLite WAL mode: https://sqlite.org/wal.html
- SQLite concurrent write limitations: https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/
- MQTT rules engine reference implementation: https://github.com/phyunsj/mqtt-rule-engine
- HABApp Python MQTT rules engine (reference): https://habapp.readthedocs.io/en/0.20.2/about_habapp.html
- MQTT to webhook patterns: https://www.emqx.com/en/blog/mqtt-to-webhook
- High-frequency MQTT React dashboard: https://akpolatcem.medium.com/from-python-simulation-to-react-visualization-building-a-real-time-flight-data-dashboard-with-mqtt-83a9d2a44303
- Modular monolith in Python: https://breadcrumbscollector.tech/modular-monolith-in-python/
- Python plugin architecture: https://mathieularose.com/plugin-architecture-in-python

---
*Architecture research for: MQTT web interface with automation/agency capabilities*
*Researched: 2026-03-24*
