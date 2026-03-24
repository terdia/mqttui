# Pitfalls Research

**Domain:** MQTT web interface with automation rules engine, plugin architecture, modern frontend
**Researched:** 2026-03-24
**Confidence:** HIGH (critical pitfalls verified against official docs and community post-mortems)

---

## Critical Pitfalls

### Pitfall 1: Rules Engine Feedback Loops — MQTT Publishes Triggering Itself

**What goes wrong:**
An automation rule subscribes to topic `sensors/temperature`, evaluates a condition, then publishes a command to `actuators/hvac`. If the HVAC publishes a confirmation back on a topic that another rule monitors, and that rule publishes again, a publish chain forms. With wildcard subscriptions (`#`) and rules that publish to topics the app already subscribes to, one message can cascade into thousands per second, saturating the broker and crashing the app. This is the #1 reported issue in Node-RED MQTT automation forums.

**Why it happens:**
Developers model rules as simple if-then pairs without thinking about the full message graph. When `MQTT_TOPICS` is `#`, the rules engine receives every message the app itself publishes. With multiple rules sharing overlapping topic patterns, a message satisfying Rule A triggers Rule B's condition, which publishes something Rule A matches again.

**How to avoid:**
- Assign every automated publish a metadata header (MQTT v5 user properties, or a reserved JSON key like `__source: "mqttui-automation"`) and skip rules evaluation for messages with that marker.
- Implement a per-rule execution counter within a rolling time window (e.g., max 10 firings per rule per minute). Disable the rule and alert the user when the limit is hit.
- Reject rules where the trigger topic pattern matches the action topic (exact or wildcard overlap check at rule-save time, not at runtime).
- Add a global circuit breaker: if total automation-triggered publishes exceed N per second, pause all rule evaluation and surface an error in the UI.

**Warning signs:**
- MQTT broker logs showing rapid repeated identical messages
- `on_message` callback invocation rate climbing without new device activity
- SQLite write lock contention errors appearing during seemingly idle periods
- Memory usage climbing steadily after a rule is enabled

**Phase to address:** Automation Rules Engine (first phase implementing rules). The data model and execution engine must include loop prevention before any rule can trigger a publish.

---

### Pitfall 2: Eventlet Deprecation Making the Entire Async Core Unmaintainable

**What goes wrong:**
The current stack pins `eventlet==0.30.2`. Eventlet is officially in maintenance mode ("life support") — new feature development is stalled, Python 3.10+ compatibility is broken, and security patches are not guaranteed. When adding async-heavy features (rules execution, plugin hooks, webhook delivery), blocking calls inside eventlet's cooperative threading model cause silent hangs. Specifically: `eventlet.monkey_patch()` interferes with standard `threading.Thread` in Python 3.8+, causing `thread.start()` to block indefinitely in some configurations.

**Why it happens:**
Eventlet was chosen because Flask-SocketIO required it for WebSocket support. The project is locked to `eventlet==0.30.2` with `Flask==2.0.1` and `Flask-SocketIO==5.1.1` — a frozen stack that predates the eventlet deprecation decision. New features added on top of this stack inherit its fragility.

**How to avoid:**
- Migrate to `gevent` or the `threading` async mode (`async_mode='threading'` in SocketIO) before adding any new async features. The `threading` mode is actively maintained and has no monkey patching requirements.
- Pin `Flask-SocketIO` to 5.3+ which supports all three async modes without eventlet-specific workarounds.
- If staying on eventlet temporarily, never introduce `threading.Thread` directly — use `eventlet.spawn()` or `eventlet.GreenPool` consistently throughout new code.
- Audit the plugin execution model: plugins that use `requests`, `subprocess`, or `time.sleep` inside an eventlet context will block the entire server without error.

**Warning signs:**
- Server stops accepting new WebSocket connections after a few hours of uptime (eventlet idle hang)
- `pytest` hangs when tests import `app.py` (eventlet monkey patching interfering with multiprocessing in test runners)
- `DeprecationWarning` from eventlet appearing in logs after Python 3.9+

**Phase to address:** Performance & Architecture phase (before adding rules engine or plugins). Switching async mode is a cross-cutting change that becomes much harder after new async features are layered on top.

---

### Pitfall 3: Plugin System Executing Untrusted Python in the Main Process

**What goes wrong:**
A plugin architecture that uses `exec()`, `eval()`, or `importlib.import_module()` on user-supplied plugin files runs that code in the same Python process as the Flask app. A malicious or buggy plugin can: read/overwrite `messages`, `topics`, and the SQLite database directly; call `mqtt_client.publish()` to any topic; access `os.environ` (exposing `MQTT_USERNAME`, `MQTT_PASSWORD`, `SECRET_KEY`); or cause an unhandled exception that crashes the entire server. Python's object hierarchy makes true in-process sandboxing effectively impossible — every sandbox approach has documented bypass techniques.

**Why it happens:**
The simplest plugin architecture is `importlib.import_module(plugin_path)` followed by calling a hook function. It feels safe because it's "just Python imports," but it offers zero isolation. CVE-2025-68668 (CVSS 9.9) demonstrates this exact attack vector against n8n's Python code execution node.

**How to avoid:**
- Run plugins in isolated subprocesses with `subprocess.run(['python', plugin_script], timeout=30)`, communicating via stdin/stdout JSON, not shared memory.
- Define a strict plugin API: plugins receive a serialized message dict and return a serialized action dict — no direct access to application objects.
- Apply filesystem restrictions: plugins execute in a dedicated temp directory with no access to the application directory.
- Validate plugin output against a schema before acting on it.
- For in-process plugins (performance-critical cases only): use `RestrictedPython` + explicit allowlist of permitted builtins — never blacklist.

**Warning signs:**
- Plugin API design that passes `mqtt_client`, `db`, or `app` objects as arguments to plugin hooks
- Plugin documentation showing examples of `import flask` or `import sqlite3` within a plugin
- No timeout on plugin hook execution

**Phase to address:** Plugin Architecture phase. The subprocess boundary must be in the design from day one — retrofitting it after plugins ship creates a breaking API change.

---

### Pitfall 4: Flask + SQLite "Database is Locked" Errors Under Automation Load

**What goes wrong:**
The current `database.py` uses thread-local SQLite connections (`threading.local()`), which is correct for the current single-MQTT-callback model. But an automation rules engine introduces concurrent writers: the MQTT `on_message` callback writes incoming messages while simultaneously rule actions trigger writes (publish confirmations, rule execution logs, alert records). SQLite's WAL mode allows one writer at a time — additional concurrent writers receive `sqlite3.OperationalError: database is locked` immediately unless `busy_timeout` is set. At 1000+ msg/sec (a stated project requirement), this becomes a bottleneck.

**Why it happens:**
The current code sets `timeout=30.0` on the connection, which helps for reads, but does not set `PRAGMA busy_timeout` at the database level. More importantly, each automation rule action and each webhook delivery creates a new write transaction contending with the message ingest path. Thread-local connections mean each new thread (rule executor, webhook worker) creates its own connection with no coordination.

**How to avoid:**
- Enable WAL mode explicitly: `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` on every new connection.
- Set `PRAGMA busy_timeout=5000` (5 seconds) to allow writers to queue rather than fail immediately.
- Separate the write paths: use a single writer thread (or asyncio queue) for all database writes. The MQTT callback and rule engine both enqueue to this writer, which processes serially.
- For the automation engine, batch rule execution log writes — write asynchronously after the rule fires, not inline in the message handler.
- Add a migration to enable WAL mode on existing user databases without data loss (it's online and safe).

**Warning signs:**
- `sqlite3.OperationalError: database is locked` appearing in logs
- Message throughput dropping when rules are enabled vs. disabled
- Increasing `store_message()` failure rate visible in logs

**Phase to address:** Automation Rules Engine phase (introduce WAL mode and the write queue before rules go in). Also add busy_timeout to the existing database.py immediately as a low-risk improvement.

---

### Pitfall 5: Real-Time UI Flooding — Unbatched Socket.IO Emissions Saturating the Browser

**What goes wrong:**
`socketio.emit('mqtt_message', message)` is called on every single MQTT message received, directly in `on_message`. At 1000 msg/sec, this sends 1000 Socket.IO frames per second to every connected browser. React/Vue components that re-render on each message will hit 60fps rendering limits and queue a backlog of events, causing the browser tab to become unresponsive within seconds. The current vanilla JS frontend avoids this problem only because it appends to a list instead of re-rendering a tree, but a modern component-based frontend will trigger full reconciliation on each event.

**Why it happens:**
The emit-on-every-message pattern works fine at 1-10 msg/sec (typical IoT sensor rate). Developers test at low rates and ship. High-throughput brokers (industrial MQTT, telemetry aggregators) expose the problem immediately in production.

**How to avoid:**
- Implement server-side batching: accumulate messages for 100ms (configurable), then emit a single `mqtt_messages_batch` event containing an array. This reduces 1000 Socket.IO events/sec to 10 batch events/sec.
- Add a client-side rate limiter: the UI processes at most N messages per render cycle, dropping or coalescing older messages of the same topic if the queue grows.
- For the modern frontend: use virtualized lists (react-window or @tanstack/virtual) for the message feed — rendering 5000 DOM nodes kills any browser.
- Expose a `max_emit_rate` environment variable so users can tune the batch interval for their broker's throughput.
- The existing in-memory `messages` list is capped at 100 — the batch buffer should respect a similar cap to avoid unbounded memory growth between flushes.

**Warning signs:**
- Browser DevTools showing Socket.IO event queue growing during high message rate
- UI frame rate dropping below 30fps when more than ~50 messages/sec arrive
- `active_websockets > 5` combined with high message rate causes server CPU to spike

**Phase to address:** Modern Frontend phase. The batching must be implemented server-side before the frontend migration, because the new component framework will be far more sensitive to emit frequency than the current vanilla JS.

---

### Pitfall 6: paho-mqtt 1.5.1 Callback API Incompatible with paho-mqtt 2.x

**What goes wrong:**
The project pins `paho-mqtt==1.5.1`. paho-mqtt 2.0 introduced `CallbackAPIVersion` as a required argument to `mqtt.Client()` and changed the signature of `on_connect`, `on_disconnect`, and `on_message` callbacks. Users who `pip install paho-mqtt` without a pinned version get 2.x and the app fails with `TypeError: on_connect() takes 4 positional arguments but 5 were given` or the newer `Unsupported callback API version` error. paho-mqtt 2.1 issues `DeprecationWarning` for every connection using the old API. paho-mqtt 3.0 (planned) will remove VERSION1 entirely.

**Why it happens:**
The current `requirements.txt` pins `paho-mqtt==1.5.1` which protects existing Docker images. But anyone building from source without the exact requirements, or any downstream project depending on this library, will silently upgrade. The `on_connect` in `app.py` already handles `properties=None` for MQTTv5 compatibility — but the paho 2.x `CallbackAPIVersion.VERSION2` changes argument order again.

**How to avoid:**
- Migrate to `CallbackAPIVersion.VERSION2` API now, as part of the dependency modernization phase. This is a one-time surgical change to the three callback functions.
- Update `requirements.txt` to `paho-mqtt>=2.0,<3.0` with the migrated callbacks.
- Add a version check in startup logging so users can see which paho version is active.
- Test the MQTT v3.1.1 and v5 paths explicitly after migration — the VERSION2 API provides reason codes for both, but the argument positions differ from VERSION1.

**Warning signs:**
- `DeprecationWarning: Callback API version 1 is deprecated` in logs when running paho >= 2.1
- CI/CD pipelines not pinning `paho-mqtt` and failing intermittently after a new release
- Users reporting `TypeError` when installing without Docker

**Phase to address:** Dependency modernization / Testing Infrastructure phase. Fix before adding any new MQTT-specific features that depend on callback behavior.

---

### Pitfall 7: Docker Upgrade Breaking Existing User Deployments

**What goes wrong:**
Existing users run `docker pull terdia07/mqttui` and restart their containers, expecting zero configuration changes. If a new version renames environment variables (e.g., `DB_PATH` to `MQTT_DB_PATH`), changes default values, or removes a previously supported variable, their containers silently use defaults and lose previously-working configurations. This is a silent failure — the app starts without error but behaves differently. The SQLite database path change is particularly dangerous: a new `DB_PATH` default means the app creates a fresh database and loses all historical messages.

**Why it happens:**
Developers rename variables for clarity during a refactor without checking what existing deployments use. Docker containers rely on environment variables as their configuration contract — there's no migration mechanism built in.

**How to avoid:**
- Treat every environment variable name as a public API — never rename, only add aliases.
- For the plugin architecture and rules engine, introduce new namespaced variables (`RULES_*`, `PLUGIN_*`) rather than modifying existing ones.
- Add startup validation: log a clear `ERROR` (not just a warning) when deprecated variable names are detected, with instructions for the new name.
- Version the configuration schema and document all breaking changes in `CHANGELOG.md` with a migration note.
- The Docker Hub image should maintain a `latest` tag pointing to the most recent stable release, with explicit `v2.x` tags for users who need to pin.

**Warning signs:**
- A refactoring PR that changes any `os.getenv(` call to use a different key name
- No mention of backward compatibility in a PR that modifies environment variable defaults
- New features that require new mandatory environment variables with no defaults

**Phase to address:** Every phase. Establish the convention before any new env vars are added.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Storing rules engine state in SQLite alongside messages | No new infrastructure | Rules evaluation blocks on message write lock; schema migrations needed for rules changes | Never — rules state belongs in a separate table with its own write path |
| Using `exec(plugin_code)` for plugins | Zero subprocess overhead | Full host access for any plugin; impossible to sandbox later | Never |
| Emitting every MQTT message as a Socket.IO event | Simplest code path | UI unresponsive at high message rates; can't be fixed client-side only | Only if max message rate is known to be < 20/sec |
| Keeping eventlet as async mode through v2 | No migration work | Incompatible with Python 3.10+; no security patches; blocks gevent-based features | Only if the Python version is pinned to 3.9 and no new async features are added |
| In-memory `messages` list as primary data source | Fast reads | Lost on restart, max 100 messages, race condition on concurrent access | Only as a fallback when DB is disabled, never as primary |
| Running automation rules synchronously in `on_message` | Simple implementation | Blocks MQTT message processing; slow rules create message backlog | Never — rules must run in a separate worker pool |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| paho-mqtt + eventlet | Calling `mqtt_client.loop_start()` inside an eventlet context; the blocking loop fights the green thread scheduler | Use `mqtt_client.loop_start()` only once and rely on eventlet's I/O to handle the MQTT socket, or migrate to threading mode where `loop_start()` uses a real OS thread |
| SQLite + threading | Creating one connection per thread without enabling WAL mode; threads serialize on writes without backpressure | Enable `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`; use a single write queue |
| Socket.IO + multiple Gunicorn workers | Broadcasting to all clients fails — only clients on the worker that called `emit()` receive the message | Either stay single-worker or add Redis message queue with `pip install flask-socketio[redis]` |
| Webhook delivery in MQTT callback | Blocking HTTP call inside `on_message` delays all subsequent MQTT message processing | Enqueue webhook jobs to a background thread pool; never block `on_message` |
| React/Vue + Socket.IO | Direct `socket.on('mqtt_message', setState)` causes a re-render on every message | Buffer incoming messages in a ref, flush to state on animation frame or fixed interval |
| Plugin hooks + SQLite | Plugin code calls `db.store_message()` directly, creating write contention | Plugin API returns an action object; the main process decides whether and how to persist it |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `_cleanup_old_messages()` called on every `store_message()` | COUNT(*) query on every write; write throughput drops as DB grows | Run cleanup on a background timer (every 5 minutes), not inline with writes | ~10,000 messages in the database |
| Python-level JSON path filtering in `get_messages()` | API response latency grows with message count; all messages loaded into memory for Python filtering | Add proper SQLite JSON1 extension queries or accept that JSON path filter is slow and document it | ~1,000 messages in a filtered query |
| Topic regex filtering using Python `re` after SQL fetch | All messages fetched from DB into Python before regex is applied | Apply REGEXP in SQL (already done via `create_function`) but ensure index exists on `topic` column | ~5,000 messages per query |
| `socketio.emit()` called from MQTT callback without batching | CPU spike on server; browser event queue saturation; UI freeze | Server-side 100ms batch window | > 50 msg/sec sustained |
| In-memory `messages` list is shared global state written from MQTT thread and read from HTTP thread | Intermittent IndexError or stale data under concurrent load | Replace with `collections.deque(maxlen=100)` which is thread-safe for append/pop operations | Any concurrent load; currently undetected at low traffic |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `SECRET_KEY` defaults to `'your-secret-key'` in production | Session forgery; anyone can craft valid Flask session cookies | Require `SECRET_KEY` at startup and refuse to start if it equals the default; generate via `secrets.token_hex(32)` |
| MQTT credentials logged at INFO level (`mqtt_username if mqtt_username else 'Not set'`) | Credentials appear in log files and Docker stdout | Log presence/absence only, never value; redact from debug bar output |
| Plugin files loaded from user-configurable path without path traversal check | Plugin path `../../etc/passwd` or `../../app.py` could expose arbitrary files | Resolve and validate plugin paths against an allowed directory using `pathlib.Path.resolve()` |
| No rate limiting on `/publish` endpoint | Unauthenticated callers can flood any MQTT topic | Add per-IP rate limiting before authentication is implemented |
| Webhook URLs stored in rules engine without SSRF validation | Rules engine could be used to probe internal network endpoints | Validate webhook URLs against an allowlist or block RFC-1918 and loopback addresses |
| `eval()` or `exec()` in rule condition evaluation (common shortcut) | Arbitrary code execution if conditions are user-supplied | Use a safe expression library (`simpleeval`) or a restricted DSL, never raw Python eval |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Rules silently disabled due to loop detection with no notification | User thinks automation is working; nothing happens | Surface rule status prominently: active/paused/error with reason in the UI |
| No way to test a rule before enabling it | Rules with typos fire against live broker, publishing wrong values | Provide a "dry run" mode that evaluates the rule against recent message history without publishing |
| Plugin install with no output until the page is refreshed | User double-clicks install; two instances load | Show installation progress inline; disable install button during operation |
| Message feed shows raw MQTT payloads without topic context for automated messages | Impossible to distinguish automation noise from real device traffic | Tag automated messages with a visual indicator in the message feed |
| Analytics dashboard that auto-refreshes without user control | Disorienting in the middle of debugging a rule | Make refresh interval configurable; default to manual refresh for analytics, automatic for live feed |

---

## "Looks Done But Isn't" Checklist

- [ ] **Rules Engine:** Often missing loop detection — verify that a rule subscribing to a topic that its action publishes to is either blocked at save time or protected by a circuit breaker at runtime.
- [ ] **Plugin System:** Often missing subprocess isolation — verify that a plugin that calls `import os; os.system('rm -rf /')` cannot execute against the host filesystem.
- [ ] **MQTT Reconnection:** Often missing exponential backoff — verify that the current `time.sleep(5); connect_mqtt()` recursive retry in `on_connect` does not cause a stack overflow after extended broker downtime (currently unbounded recursion).
- [ ] **Socket.IO Scaling:** Often missing Redis message queue when adding features that broadcast to all clients — verify that `socketio.emit()` called from a background thread (rule executor, webhook worker) actually reaches all connected clients, not just those on the same eventlet greenlet.
- [ ] **Database WAL Mode:** Often missing on existing user databases — verify that WAL mode is enabled on startup migration, not just on fresh databases.
- [ ] **Frontend Migration:** Often missing catch-all Flask route for SPA — verify that refreshing a SPA route (e.g., `/rules/123`) returns `index.html` and not a Flask 404.
- [ ] **Webhook Delivery:** Often missing idempotency — verify that a webhook fired twice for the same MQTT message does not cause duplicate actions on the receiving end.
- [ ] **paho-mqtt Version:** Often missing callback API version migration — verify behavior under paho-mqtt 2.x before tagging a release.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Rules feedback loop has flooded broker | MEDIUM | 1. Disable all rules via feature flag env var `RULES_ENABLED=false`. 2. Restart app. 3. Inspect rule action topics vs. subscription topics in the rules table. 4. Add per-rule rate limit before re-enabling. |
| Plugin corrupted SQLite database | HIGH | 1. Stop app. 2. Restore from last backup (if any — add backups). 3. Rebuild plugins as subprocess-isolated. 4. Note: no built-in backup currently exists — add `db.backup()` call on startup. |
| eventlet hang causing server to stop accepting connections | LOW | 1. Restart container. 2. Long-term: migrate async mode to threading. 3. Add a health check endpoint and Docker `HEALTHCHECK` directive so the container auto-restarts. |
| Frontend migration broke Socket.IO connection | MEDIUM | 1. Check that the SPA is connecting to the same origin (not hardcoded port). 2. Verify CORS settings in `SocketIO(app, cors_allowed_origins=...)`. 3. Check that catch-all Flask route does not intercept `/socket.io/` path. |
| paho-mqtt 2.x upgrade broke callbacks | LOW | 1. Add `CallbackAPIVersion.VERSION1` as first arg to `mqtt.Client()` for immediate fix. 2. Properly migrate to VERSION2 before 3.0 removes VERSION1. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Rules engine feedback loops | Automation Rules Engine | Integration test: rule that publishes to its own trigger topic runs for 10 seconds; verify publish count stays at 1 |
| Eventlet deprecation | Architecture Modernization (before Rules Engine) | `async_mode='threading'` in SocketIO init; no eventlet import in codebase; Python 3.11 compatibility test passes |
| Plugin in-process execution | Plugin Architecture | Security test: plugin calling `os.getenv('MQTT_PASSWORD')` returns `None` or raises `PermissionError`; plugin calling `sys.exit()` does not crash the main process |
| SQLite write contention | Automation Rules Engine (pre-work) | Load test: 500 msg/sec sustained for 60 seconds; zero `database is locked` errors in logs |
| Real-time UI flooding | Modern Frontend (server-side prep before frontend migration) | Load test: 1000 msg/sec; browser CPU stays below 50%; UI remains responsive (no jank) |
| paho-mqtt callback API | Dependency Modernization / Testing Infrastructure | Unit test: app starts cleanly under paho-mqtt 2.1; no DeprecationWarning in logs |
| Docker upgrade compatibility | Every phase | Changelog entry for every env var change; regression test: existing `docker-compose.yml` with current env vars works unchanged after upgrade |
| Unbounded recursion in MQTT reconnect | Testing Infrastructure | Simulate 60-second broker outage; verify app does not throw `RecursionError`; verify reconnect uses exponential backoff |

---

## Sources

- Flask-SocketIO deployment documentation (single worker limitation, message queue requirements): https://flask-socketio.readthedocs.io/en/latest/deployment.html
- Flask-SocketIO issues on eventlet deprecation and monkey patching: https://github.com/miguelgrinberg/Flask-SocketIO/issues/1264
- Node-RED forum: MQTT automation infinite loops and prevention patterns: https://discourse.nodered.org/t/trouble-with-mqtt-automation-creating-endless-loops/39090
- paho-mqtt 2.0 migration guide and breaking callback API changes: https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html
- SQLite concurrent writes and "database is locked" errors: https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/
- Python sandboxing impossibility (Checkmarx): https://checkmarx.com/zero-post/glass-sandbox-complexity-of-python-sandboxing/
- CVE-2025-68668: in-process Python code execution sandbox bypass in n8n: https://socradar.io/blog/cve-2025-68668-n8n-python-code-node/
- Socket.IO performance tuning (batching, deduplication, virtualization): https://socket.io/docs/v4/performance-tuning/
- SQLite WAL mode high-throughput strategies: https://dev.to/software_mvp-factory/sqlite-wal-mode-and-connection-strategies-for-high-throughput-mobile-apps-beyond-the-basics-eh0
- Eventlet maintenance mode status and Python 3.10+ incompatibility: https://dev.to/deepak_mishra_35863517037/the-async-core-understanding-eventlet-and-gevent-in-flask-socketio-2b2f
- NVIDIA: sandboxing agentic/plugin workflows: https://developer.nvidia.com/blog/practical-security-guidance-for-sandboxing-agentic-workflows-and-managing-execution-risk/

---
*Pitfalls research for: MQTT web interface automation and plugin expansion (mqttui v2)*
*Researched: 2026-03-24*
