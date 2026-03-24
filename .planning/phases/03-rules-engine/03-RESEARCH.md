# Phase 3: Rules Engine - Research

**Researched:** 2026-03-24
**Domain:** Python rules engine / ECA (Event-Condition-Action) / APScheduler / paho-mqtt wildcard matching
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Condition Evaluator DSL**
- Structured JSON conditions, NOT eval/exec (security)
- Supported operators: eq, ne, gt, lt, gte, lte, contains, not_contains, regex, exists, not_exists
- Condition format: `{"path": "temperature", "op": "gt", "value": 30}`
- Nested JSON path support using dot notation: `"sensors.outdoor.temp"`
- Compound conditions: `{"all": [...conditions]}` and `{"any": [...conditions]}`
- Payload parsed as JSON when possible; raw string comparison as fallback
- Condition evaluator is a pure function: `evaluate(condition_dict, payload_dict) -> bool`

**Topic Matching**
- Use `paho.mqtt.matcher` (MQTTMatcher) for MQTT wildcard support (+, #)
- Rule trigger_topic supports standard MQTT wildcards: `sensors/+/temp`, `home/#`
- Exact match and wildcard match both supported

**Action Types**
- **publish**: Publish to a topic with configurable payload, QoS, retain flag. Marked with `__source: "mqttui-automation"` in payload metadata
- **webhook**: HTTP POST to URL (stub in Phase 3 — full implementation in Phase 4)
- **log**: Log to alert_history table with severity level and message
- Action format: `{"type": "publish", "topic": "alerts/temp", "payload": "{\"alert\": true}", "qos": 1, "retain": false}`

**Loop Prevention (Critical)**
- All automation publishes include `__source: "mqttui-automation"` marker in message metadata
- Messages with `__source` marker are SKIPPED during rule evaluation (prevents feedback loops)
- Per-rule rate limit: max 10 firings per minute (configurable per rule, stored in rule model)
- Global circuit breaker: max 100 total rule firings per minute across all rules
- Circuit breaker auto-resets after 60 seconds of no new firings
- Rate limit state tracked in-memory (dict of `rule_id -> deque of timestamps`)

**Rule Data Model (SQLAlchemy)**
- `Rule(id, name, description, trigger_topic, condition_json, action_json, enabled, rate_limit_per_min, schedule_cron, last_fired, fire_count, created_at, updated_at)`
- `condition_json`: JSON string of condition dict
- `action_json`: JSON string of action dict
- `enabled`: boolean, default True
- `rate_limit_per_min`: integer, default 10
- `schedule_cron`: optional cron expression for time-based rules (null = event-driven only)

**Time-Based Scheduling**
- APScheduler 3.x with SQLite job store (shared database)
- Cron-style schedule expressions: `"*/5 * * * *"` for every 5 minutes
- Time-based rules fire actions on schedule regardless of incoming messages
- Schedule changes take effect on next scheduler tick (no restart needed)

**Hot Reload**
- Rules loaded from DB into in-memory cache on startup
- Cache invalidated on any rule CRUD operation via REST API
- No application restart required for rule changes
- Signal `rule_changed` fires on CRUD to notify subscribers

**REST API (under /api/v1/rules)**
- GET /api/v1/rules — list all rules
- POST /api/v1/rules — create new rule
- GET /api/v1/rules/\<id\> — get rule by ID
- PUT /api/v1/rules/\<id\> — update rule
- DELETE /api/v1/rules/\<id\> — delete rule
- POST /api/v1/rules/\<id\>/enable — enable rule
- POST /api/v1/rules/\<id\>/disable — disable rule
- POST /api/v1/rules/\<id\>/test — dry-run rule against a sample payload (returns match result + would-fire actions)

### Claude's Discretion
- Exact module file structure within mqttui/ for rules engine
- Error handling strategy for malformed conditions
- Whether to use a separate RuleEngine class or module-level functions
- APScheduler configuration details (misfire grace time, max instances)
- Exact format of `__source` marker (property vs payload field)

### Deferred Ideas (OUT OF SCOPE)
- Message transformation pipelines (JSONata expressions) — Phase 4+
- Complex stateful conditions ("value increasing for 5 consecutive messages") — v2.x
- Visual rule builder UI — Phase 5 (frontend) will add form-based rule editor
- Rule templates/presets — quality-of-life, add after core rules ship
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RULE-01 | User can create automation rule with topic pattern trigger and payload condition | Rule SQLAlchemy model + REST CRUD; MQTTMatcher for topic wildcards; JSON condition evaluator |
| RULE-02 | User can define rule actions: publish to topic, trigger webhook, or log alert | ActionExecutor dispatches by type; webhook stub returns immediately in Phase 3 |
| RULE-03 | Rules evaluate against incoming MQTT messages in real-time | Subscribe to `mqtt_message_received` blinker signal; evaluate in-memory cache against each message |
| RULE-04 | Rules engine includes loop detection with per-rule rate limiting and global circuit breaker | `__source` marker skip; per-rule deque rate limit; global counter circuit breaker |
| RULE-05 | User can enable/disable individual rules without deleting them | `enabled` column + POST /enable, /disable endpoints; cache filters disabled rules |
| RULE-06 | User can create time-based rules (fire at schedule, e.g., publish heartbeat every 5 minutes) | APScheduler 3.11.2 GeventScheduler + SQLAlchemyJobStore; CronTrigger.from_crontab() |
| RULE-07 | Rules hot-reload from database without application restart | In-memory cache dict; invalidated on CRUD; blinker `rule_changed` signal triggers reload |
| RULE-08 | Rule CRUD available via REST API endpoints | 8 endpoints on api_v1 blueprint or new rules blueprint; follows established JSON envelope pattern |
</phase_requirements>

---

## Summary

Phase 3 builds a custom ECA (Event-Condition-Action) rules engine directly integrated into the existing Flask/gevent/blinker architecture. The engine has two input paths: (1) real-time evaluation triggered by the `mqtt_message_received` blinker signal, and (2) time-based firing via APScheduler GeventScheduler. All state flows through an in-memory rule cache backed by SQLAlchemy, with hot-reload on any CRUD operation.

The condition evaluator is a custom pure-function interpreter (~150-200 lines) operating on structured JSON — this is the correct and locked approach over `eval`/`simpleeval`/`jsonata`. Topic matching uses `paho.mqtt.matcher.MQTTMatcher` (already bundled with paho-mqtt 2.1.0, confirmed present) which provides a trie-based wildcard matcher with an `iter_match(topic)` generator interface.

The primary new dependency is `APScheduler[gevent,sqlalchemy]==3.11.2`. Since this app uses `gevent` as the SocketIO/WSGI mode (confirmed in `app.py`), the scheduler MUST use `GeventScheduler` rather than `BackgroundScheduler` to avoid threading/greenlet conflicts. Jobs must wrap Flask DB calls in `with app.app_context():`. The SQLite job store can reuse the existing `mqttui_users.db` URI or a separate `mqttui_rules.db`.

**Primary recommendation:** Build a `RuleEngine` class in `mqttui/rules/engine.py` that owns the cache, the MQTTMatcher, the rate-limit deques, and the GeventScheduler. Initialize it in `create_app()` and register its `on_mqtt_message` handler to the blinker signal at startup.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.11.2 | Time-based rule scheduling with SQLite persistence | Official latest (released 2025-12-22); GeventScheduler for gevent apps; SQLAlchemyJobStore for cron persistence |
| paho-mqtt (matcher) | 2.1.0 (already installed) | MQTT wildcard topic matching (+, #) | MQTTMatcher is bundled inside paho-mqtt; confirmed available; uses trie for O(depth) matching |
| Flask-SQLAlchemy (sa) | 3.1.1 (already installed) | Rule model persistence | Already used for User model; Rule follows same pattern |
| blinker | 1.9.0 (already installed) | Event bus: mqtt_message_received, rule_fired, rule_changed | Already wired in events.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| collections.deque | stdlib | Sliding-window rate limit: `deque(maxlen=N)` timestamps | Per-rule and global circuit breaker tracking |
| re (regex module) | stdlib | Regex operator in condition evaluator | When condition op == "regex" |
| json | stdlib | Deserialize condition_json/action_json from DB | Every rule load/cache fill |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom JSON condition evaluator | simpleeval | simpleeval is too permissive for untrusted input; custom evaluator is ~200 lines, handles exact operators needed, no attack surface |
| Custom JSON condition evaluator | jsonata / jsonpath-ng | Overkill and untrusted eval risk; dot notation path resolution is 5-10 lines of Python split+reduce |
| GeventScheduler | BackgroundScheduler | BackgroundScheduler spawns threads; gevent monkey-patches threading, causing potential deadlocks. GeventScheduler uses greenlets natively — correct choice for this app |
| Separate rules DB | Reuse mqttui_users.db | Either works; separate DB avoids schema coupling; decision left to implementer |

**Installation (new dependency only):**
```bash
pip install "APScheduler[gevent,sqlalchemy]==3.11.2"
```

**Version verification (run before planning):**
APScheduler 3.11.2 confirmed as latest stable — released 2025-12-22 per PyPI. Previous training-data assumption of 3.10.x was stale.

---

## Architecture Patterns

### Recommended Project Structure
```
mqttui/
├── rules/
│   ├── __init__.py          # exports RuleEngine
│   ├── engine.py            # RuleEngine class: cache, matcher, rate limits, scheduler
│   ├── evaluator.py         # evaluate(condition_dict, payload_dict) -> bool (pure function)
│   ├── actions.py           # execute_action(action_dict, context) -> None
│   └── models.py            # Rule SQLAlchemy model (or add to mqttui/models.py)
├── routes/
│   └── rules.py             # Blueprint: /api/v1/rules CRUD
```

### Pattern 1: MQTTMatcher Cache
**What:** Maintain a single MQTTMatcher instance in the RuleEngine. When the rule cache is rebuilt, re-populate the matcher. Each rule registers its `trigger_topic` as a key mapping to the Rule object (or rule_id).
**When to use:** On engine startup and on every cache invalidation.

```python
# Source: paho.mqtt.matcher - confirmed working via local Python 3 test
from paho.mqtt.matcher import MQTTMatcher

class RuleEngine:
    def _rebuild_cache(self):
        self._matcher = MQTTMatcher()
        self._rules = {}
        for rule in Rule.query.filter_by(enabled=True).all():
            self._rules[rule.id] = rule
            self._matcher[rule.trigger_topic] = rule.id

    def on_mqtt_message(self, sender, **kwargs):
        topic = kwargs['topic']
        payload_str = kwargs['payload']
        # Loop prevention: skip automation-sourced messages
        try:
            payload_dict = json.loads(payload_str)
            if isinstance(payload_dict, dict) and payload_dict.get('__source') == 'mqttui-automation':
                return
        except (json.JSONDecodeError, AttributeError):
            payload_dict = None
        # Match rules
        for rule_id in self._matcher.iter_match(topic):
            rule = self._rules.get(rule_id)
            if rule and self._check_rate_limit(rule):
                self._evaluate_and_fire(rule, topic, payload_str, payload_dict)
```

### Pattern 2: Pure-Function Condition Evaluator
**What:** A recursive pure function that interprets a structured JSON condition dict against a payload dict. No `eval`, no external library.
**When to use:** Called for every rule match.

```python
# Source: custom implementation — pattern based on CONTEXT.md spec
import re
import json

def _get_path(data, path):
    """Resolve dot-notation path against dict. Returns value or raises KeyError."""
    parts = path.split('.')
    node = data
    for part in parts:
        if not isinstance(node, dict):
            raise KeyError(path)
        node = node[part]
    return node

def evaluate(condition, payload):
    """
    Evaluate a condition dict against a payload dict.
    Returns bool. Raises ConditionError on malformed condition.
    payload: dict (parsed JSON) or None (raw string payload).
    """
    if 'all' in condition:
        return all(evaluate(c, payload) for c in condition['all'])
    if 'any' in condition:
        return any(evaluate(c, payload) for c in condition['any'])

    path = condition.get('path')
    op = condition.get('op')
    value = condition.get('value')

    if op == 'exists':
        try:
            _get_path(payload, path)
            return True
        except (KeyError, TypeError):
            return False

    if op == 'not_exists':
        try:
            _get_path(payload, path)
            return False
        except (KeyError, TypeError):
            return True

    try:
        actual = _get_path(payload, path)
    except (KeyError, TypeError):
        return False

    if op == 'eq':     return actual == value
    if op == 'ne':     return actual != value
    if op == 'gt':     return actual > value
    if op == 'lt':     return actual < value
    if op == 'gte':    return actual >= value
    if op == 'lte':    return actual <= value
    if op == 'contains':     return value in str(actual)
    if op == 'not_contains': return value not in str(actual)
    if op == 'regex':        return bool(re.search(str(value), str(actual)))

    raise ConditionError(f"Unknown operator: {op}")
```

### Pattern 3: Sliding-Window Rate Limiter (deque)
**What:** Store timestamps of recent firings in a `deque`. Before firing, evict entries older than 60 seconds. If `len(deque) >= limit`, deny firing.
**When to use:** Per-rule limit check and global circuit breaker.

```python
# Source: standard Python pattern, verified via stdlib docs
from collections import deque
from time import time

class RuleEngine:
    def __init__(self):
        self._rule_timestamps = {}     # rule_id -> deque of float timestamps
        self._global_timestamps = deque()  # global circuit breaker
        self._GLOBAL_LIMIT = 100
        self._WINDOW = 60.0

    def _check_rate_limit(self, rule):
        now = time()
        window_start = now - self._WINDOW

        # Per-rule check
        if rule.id not in self._rule_timestamps:
            self._rule_timestamps[rule.id] = deque()
        dq = self._rule_timestamps[rule.id]
        while dq and dq[0] < window_start:
            dq.popleft()
        if len(dq) >= rule.rate_limit_per_min:
            return False

        # Global circuit breaker
        while self._global_timestamps and self._global_timestamps[0] < window_start:
            self._global_timestamps.popleft()
        if len(self._global_timestamps) >= self._GLOBAL_LIMIT:
            return False

        dq.append(now)
        self._global_timestamps.append(now)
        return True
```

### Pattern 4: APScheduler GeventScheduler with SQLite and Flask App Context
**What:** Initialize GeventScheduler once in `create_app()`. For each rule with a non-null `schedule_cron`, add a job using `CronTrigger.from_crontab()`. Jobs must push Flask app context before touching SQLAlchemy.
**When to use:** Time-based rule scheduling.

```python
# Source: APScheduler 3.11.2 docs + flask-apscheduler flask_context.py example
from apscheduler.schedulers.gevent import GeventScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

def init_scheduler(app, rule_engine):
    jobstores = {
        'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])
    }
    scheduler = GeventScheduler(
        jobstores=jobstores,
        job_defaults={'misfire_grace_time': 30, 'max_instances': 1, 'coalesce': True},
    )
    scheduler.start()
    rule_engine.set_scheduler(scheduler, app)
    return scheduler

# Inside a scheduled job function (must be a module-level function for pickle):
def _fire_scheduled_rule(app, rule_id):
    with app.app_context():
        from mqttui.rules.engine import get_engine
        engine = get_engine()
        engine.fire_scheduled_rule(rule_id)
```

**Critical:** Scheduled job functions MUST be module-level (not lambdas or methods) because APScheduler pickles them for SQLite persistence. Pass `app` as the first argument, or store `app` on the rule_engine singleton and call `app.app_context()` inside the job function.

### Pattern 5: Hot-Reload on CRUD
**What:** After any rule create/update/delete, call `rule_engine.reload_cache()` and fire `rule_changed` signal. For scheduled rules, remove the old APScheduler job (if any) and re-add it.
**When to use:** In every rule CRUD route handler.

```python
# After any DB write in a route:
rule_engine.reload_cache()      # rebuilds MQTTMatcher + rule dict
rule_changed.send('api')        # blinker signal for other subscribers
# For scheduled rules:
rule_engine.sync_scheduled_jobs()  # removes/re-adds APScheduler jobs to match DB
```

### Anti-Patterns to Avoid
- **Using `BackgroundScheduler` with gevent:** Causes deadlocks. The app uses `gevent` async_mode in SocketIO. Always use `GeventScheduler`.
- **Storing lambdas as APScheduler job functions:** APScheduler pickles job functions for SQLite persistence. Lambdas and closures are not picklable. Use module-level functions with explicit `args`.
- **Sharing APScheduler jobstore between two schedulers:** APScheduler docs explicitly state jobstores cannot be shared. Use one scheduler instance, created once in `create_app()`.
- **Using `replace_existing=False` for cron jobs:** Without `replace_existing=True`, every app restart adds a duplicate job. Always pass `replace_existing=True` with an explicit `id` when using a persistent jobstore.
- **Thread-unsafe cache mutations during blinker signal delivery:** blinker signals fire synchronously in gevent greenlets. Use a simple rebuild-and-swap pattern (assign new dicts atomically) rather than mutating in-place while iterating.
- **Evaluating conditions on non-JSON payloads with path operators:** Path operators (`gt`, `lt`, etc.) require a dict. When payload is a raw string, `payload_dict` is None. The evaluator must return `False` gracefully for path-based conditions when the payload is not JSON.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MQTT wildcard matching (+ and #) | Custom regex/string matching | `paho.mqtt.matcher.MQTTMatcher` | `$SYS` topic edge cases, multi-level wildcard semantics (e.g. `$` prefix rules), already battle-tested in paho |
| Cron expression parsing/scheduling | Custom cron parser | `APScheduler CronTrigger.from_crontab()` | Handles all 5-field standard cron syntax including ranges, lists, step values; misfire tracking; persistence |
| SQLite job persistence | Raw SQL job table | `APScheduler SQLAlchemyJobStore` | Job serialization, misfire detection, timezone handling all built-in |

**Key insight:** The condition evaluator is intentionally hand-rolled because no existing library provides the exact safety/operator combination needed. Everything else (topic matching, scheduling) uses proven libraries.

---

## Common Pitfalls

### Pitfall 1: APScheduler Duplicate Jobs on Restart
**What goes wrong:** Every time the app starts, it re-adds cron jobs because the jobstore already has them. This creates duplicate firings.
**Why it happens:** APScheduler with a persistent jobstore remembers jobs between restarts. Calling `add_job()` without `replace_existing=True` adds a new entry instead of updating the existing one.
**How to avoid:** Always call `scheduler.add_job(..., id=f"rule_{rule.id}", replace_existing=True)`.
**Warning signs:** Rule fires twice per schedule tick; `apscheduler_jobs` table has duplicate `id` rows.

### Pitfall 2: GeventScheduler and `BlockingScheduler` Confusion
**What goes wrong:** Using `BackgroundScheduler` hangs the gevent event loop or causes silent job failures because it spawns OS threads that conflict with gevent's greenlet model.
**Why it happens:** The app is fully gevent-based (`socketio async_mode='gevent'`). `BackgroundScheduler` uses Python threading; gevent may or may not have monkey-patched threading.
**How to avoid:** Use `from apscheduler.schedulers.gevent import GeventScheduler`. Confirmed: APScheduler 3.11.2 ships `GeventScheduler` in `apscheduler.schedulers.gevent`.
**Warning signs:** Scheduler appears to start but jobs never fire; SocketIO connections stall after scheduler start.

### Pitfall 3: Infinite Rule Loop (Most Critical)
**What goes wrong:** Rule A triggers, publishes to topic X. Rule B listens to topic X, triggers, publishes to topic Y. Rule A listens to topic Y — infinite loop.
**Why it happens:** Rules react to all messages including those published by other rules.
**How to avoid:** The `__source: "mqttui-automation"` marker must be injected into every automation-published payload (either as a top-level JSON field, or in a metadata wrapper). The `on_mqtt_message` handler must check for this marker BEFORE evaluating any rules and return immediately if found.
**Warning signs:** Rapid repeated firings visible in logs; `fire_count` on rules increments rapidly; global circuit breaker trips.

### Pitfall 4: Non-Picklable APScheduler Job Functions
**What goes wrong:** `ValueError: Cannot serialize lambda/closure` when adding a scheduled job to SQLite jobstore.
**Why it happens:** APScheduler pickles the job callable for persistent storage. Lambda functions and closures (functions that capture variables from an enclosing scope) cannot be pickled.
**How to avoid:** Define job functions at module level in `mqttui/rules/engine.py`. Pass `rule_id` and `app` reference via `args=` or `kwargs=` parameters.
**Warning signs:** `PicklingError` or `AttributeError` on `scheduler.add_job()`.

### Pitfall 5: Cache Invalidation Race During High Message Rate
**What goes wrong:** A rule is deleted via the REST API while a blinker message handler is iterating the cache. Causes `RuntimeError: dictionary changed size during iteration` or stale references.
**Why it happens:** gevent uses cooperative multitasking. A greenlet can yield mid-iteration, allowing another greenlet to mutate the shared dict.
**How to avoid:** Use a swap pattern: build the new cache into local variables, then assign `self._rules = new_rules; self._matcher = new_matcher` atomically. Never delete or mutate the live dict while it might be iterated.
**Warning signs:** Intermittent `KeyError` or `RuntimeError` in rules engine logs under concurrent load.

### Pitfall 6: Condition Evaluator Type Coercion
**What goes wrong:** Rule condition `{"path": "temp", "op": "gt", "value": 30}` fails when the MQTT payload arrives with `{"temp": "28"}` (JSON string, not number).
**Why it happens:** JSON payloads from MQTT sensors often serialize numbers as strings. The evaluator does strict Python comparison: `"28" > 30` raises `TypeError`.
**How to avoid:** In the evaluator, attempt numeric coercion when the condition value is numeric and the actual value is a string: `try: actual = float(actual) except ValueError: pass`. Alternatively, document this behavior clearly so users know to store numeric payloads as JSON numbers.
**Warning signs:** Rules with `gt`/`lt`/`gte`/`lte` operators never fire even when payloads look correct.

---

## Code Examples

Verified patterns from official sources and confirmed working code:

### MQTTMatcher iter_match (confirmed working locally)
```python
# Source: paho-mqtt 2.1.0 installed in project; tested locally
from paho.mqtt.matcher import MQTTMatcher

matcher = MQTTMatcher()
matcher['sensors/+/temp'] = 'rule_1'
matcher['home/#'] = 'rule_2'
matcher['home/living/temp'] = 'rule_3'  # exact

list(matcher.iter_match('sensors/outdoor/temp'))  # -> ['rule_1']
list(matcher.iter_match('home/living/temp'))       # -> ['rule_2', 'rule_3']
list(matcher.iter_match('$SYS/broker/uptime'))     # -> []  ($ topics don't match wildcards)
```

### CronTrigger.from_crontab (from APScheduler 3.x docs)
```python
# Source: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html
from apscheduler.triggers.cron import CronTrigger

# Standard 5-field crontab string
trigger = CronTrigger.from_crontab('*/5 * * * *')   # every 5 minutes
trigger = CronTrigger.from_crontab('0 9 * * 1-5')   # 9am on weekdays
trigger = CronTrigger.from_crontab('30 6 1 * *')     # 6:30am on 1st of month
```

### APScheduler add_job with replace_existing (from APScheduler 3.x userguide)
```python
# Source: https://apscheduler.readthedocs.io/en/3.x/userguide.html
# "If you schedule jobs in a persistent job store during your application's initialization,
#  you MUST define an explicit ID for the job and use replace_existing=True"
scheduler.add_job(
    _fire_scheduled_rule,
    trigger=CronTrigger.from_crontab(rule.schedule_cron),
    args=[app, rule.id],
    id=f'rule_{rule.id}',
    replace_existing=True,
    misfire_grace_time=30,
    max_instances=1,
    coalesce=True,
)
```

### Flask app context inside a scheduled job
```python
# Source: flask-apscheduler examples/flask_context.py
def _fire_scheduled_rule(app, rule_id):
    """Module-level function so APScheduler can pickle it."""
    with app.app_context():
        from mqttui.rules.engine import _engine
        if _engine:
            _engine.fire_scheduled_rule(rule_id)
```

### Sliding-window rate limit (deque, stdlib)
```python
# Source: Python stdlib collections.deque; standard sliding window pattern
from collections import deque
from time import time

_timestamps = {}  # rule_id -> deque

def check_rate_limit(rule_id, limit_per_min, window=60.0):
    now = time()
    if rule_id not in _timestamps:
        _timestamps[rule_id] = deque()
    dq = _timestamps[rule_id]
    cutoff = now - window
    while dq and dq[0] < cutoff:
        dq.popleft()
    if len(dq) >= limit_per_min:
        return False
    dq.append(now)
    return True
```

### Rule SQLAlchemy model (follows existing User model pattern)
```python
# Source: project pattern — see mqttui/models.py User model
from mqttui.extensions import sa
from datetime import datetime

class Rule(sa.Model):
    __tablename__ = 'rules'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(200), nullable=False)
    description = sa.Column(sa.Text, default='')
    trigger_topic = sa.Column(sa.String(500), nullable=False)
    condition_json = sa.Column(sa.Text, nullable=False, default='{}')
    action_json = sa.Column(sa.Text, nullable=False)
    enabled = sa.Column(sa.Boolean, default=True, nullable=False)
    rate_limit_per_min = sa.Column(sa.Integer, default=10, nullable=False)
    schedule_cron = sa.Column(sa.String(100), nullable=True)
    last_fired = sa.Column(sa.DateTime, nullable=True)
    fire_count = sa.Column(sa.Integer, default=0, nullable=False)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    updated_at = sa.Column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'trigger_topic': self.trigger_topic,
            'condition': json.loads(self.condition_json) if self.condition_json else {},
            'action': json.loads(self.action_json),
            'enabled': self.enabled,
            'rate_limit_per_min': self.rate_limit_per_min,
            'schedule_cron': self.schedule_cron,
            'last_fired': self.last_fired.isoformat() if self.last_fired else None,
            'fire_count': self.fire_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| APScheduler 3.9/3.10 | APScheduler 3.11.2 | Released 2025-12-22 | Install `[gevent,sqlalchemy]` extras explicitly; no API changes for 3.x usage |
| `BackgroundScheduler` for Flask+gevent | `GeventScheduler` | APScheduler 3.x has always had it | Avoids thread/greenlet conflicts in gevent apps |
| Separate scheduler process | In-process GeventScheduler | N/A | Simpler for single-process Flask app; acceptable for this use case |

**Deprecated/outdated:**
- `apscheduler.schedulers.blocking.BlockingScheduler`: Blocks the process. Not appropriate for embedded use.
- Implicit cron field syntax (positional args) on `add_job`: Prefer `CronTrigger.from_crontab(expr)` for standard 5-field cron strings; it's clearer and accepts user-supplied strings directly.

---

## Open Questions

1. **`__source` marker format: payload field vs MQTT user properties**
   - What we know: CONTEXT.md says `__source: "mqttui-automation"` in "payload metadata"
   - What's unclear: Whether to inject into the JSON payload body itself (`{"__source": "mqttui-automation", ...original payload...}`) or as a separate wrapper (`{"__source": ..., "payload": ...}`)
   - Recommendation: Inject as a top-level field in the JSON payload. If the original payload is not JSON (raw string), wrap it: `{"__source": "mqttui-automation", "payload": "<raw>"}`. Check for `__source` key before evaluating conditions.

2. **alert_history table for `log` action type**
   - What we know: The `log` action should persist to `alert_history` table
   - What's unclear: The `alert_history` table schema is not yet defined (it appears in Phase 4 requirements ALRT-04)
   - Recommendation: In Phase 3, create a minimal `AlertHistory(id, rule_id, rule_name, topic, severity, message, fired_at)` model. Phase 4 will expand it. This unblocks the `log` action without requiring Phase 4 completion.

3. **APScheduler jobstore: separate DB vs shared `mqttui_users.db`**
   - What we know: CONTEXT.md says "SQLite job store (shared database)" and APScheduler docs warn jobstores cannot be shared between schedulers
   - What's unclear: "Shared" means shared with the same SQLAlchemy `sa` instance, not shared between schedulers. One scheduler + one SQLite DB is fine.
   - Recommendation: Use the existing `SQLALCHEMY_DATABASE_URI` (pointing to `mqttui_users.db`) so APScheduler creates its `apscheduler_jobs` table there alongside the `users` and `rules` tables. Avoids managing a second DB file.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (confirmed in `tests/` directory with conftest.py) |
| Config file | none (runs via `pytest` from project root) |
| Quick run command | `pytest tests/test_rules_engine.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RULE-01 | Rule creation via REST API persists to DB with correct fields | unit/integration | `pytest tests/test_rules_engine.py::test_create_rule -x` | Wave 0 |
| RULE-01 | Topic wildcard matching (+, #) routes messages to correct rules | unit | `pytest tests/test_rules_engine.py::test_topic_matching -x` | Wave 0 |
| RULE-02 | Publish action injects `__source` marker and calls mqtt_publish | unit | `pytest tests/test_rules_engine.py::test_publish_action -x` | Wave 0 |
| RULE-02 | Log action creates AlertHistory record | unit | `pytest tests/test_rules_engine.py::test_log_action -x` | Wave 0 |
| RULE-02 | Webhook action returns immediately (stub, does not raise) | unit | `pytest tests/test_rules_engine.py::test_webhook_stub -x` | Wave 0 |
| RULE-03 | Rules evaluate on mqtt_message_received signal in real-time | integration | `pytest tests/test_rules_engine.py::test_realtime_evaluation -x` | Wave 0 |
| RULE-03 | JSON path condition `sensors.outdoor.temp > 30` evaluates correctly | unit | `pytest tests/test_rules_engine.py::test_condition_evaluator -x` | Wave 0 |
| RULE-03 | Compound condition `{"all": [...]}` and `{"any": [...]}` work correctly | unit | `pytest tests/test_rules_engine.py::test_compound_conditions -x` | Wave 0 |
| RULE-04 | Message with `__source: "mqttui-automation"` is skipped | unit | `pytest tests/test_rules_engine.py::test_loop_prevention -x` | Wave 0 |
| RULE-04 | Per-rule rate limit prevents >N firings per minute | unit | `pytest tests/test_rules_engine.py::test_rate_limit -x` | Wave 0 |
| RULE-04 | Global circuit breaker trips at 100 firings/minute | unit | `pytest tests/test_rules_engine.py::test_circuit_breaker -x` | Wave 0 |
| RULE-05 | Disabled rule does not evaluate even when topic matches | unit | `pytest tests/test_rules_engine.py::test_disabled_rule -x` | Wave 0 |
| RULE-05 | POST /enable and /disable toggle `enabled` column | integration | `pytest tests/test_rules_api.py::test_enable_disable -x` | Wave 0 |
| RULE-06 | CronTrigger.from_crontab parses valid 5-field expression | unit | `pytest tests/test_rules_engine.py::test_cron_schedule -x` | Wave 0 |
| RULE-07 | Cache rebuilds after rule CRUD without app restart | unit | `pytest tests/test_rules_engine.py::test_hot_reload -x` | Wave 0 |
| RULE-08 | GET/POST/PUT/DELETE /api/v1/rules CRUD returns correct status codes | integration | `pytest tests/test_rules_api.py -x` | Wave 0 |
| RULE-08 | POST /api/v1/rules/\<id\>/test dry-run returns match result | integration | `pytest tests/test_rules_api.py::test_dry_run -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_rules_engine.py tests/test_rules_api.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_rules_engine.py` — unit tests for RuleEngine, condition evaluator, rate limiter, hot-reload
- [ ] `tests/test_rules_api.py` — integration tests for REST CRUD, enable/disable, dry-run endpoint
- [ ] APScheduler install: `pip install "APScheduler[gevent,sqlalchemy]==3.11.2"` — not yet in requirements.txt

---

## Sources

### Primary (HIGH confidence)
- paho-mqtt 2.1.0 `paho.mqtt.matcher` module — confirmed present and tested locally (`MQTTMatcher available`; `iter_match` confirmed working)
- [APScheduler 3.11.2 User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — scheduler types, add_job params, jobstore config, replace_existing requirement
- [APScheduler PyPI page](https://pypi.org/project/APScheduler/) — version 3.11.2 (released 2025-12-22), install extras `[gevent,sqlalchemy]`
- [APScheduler GeventScheduler module docs](https://apscheduler.readthedocs.io/en/3.x/modules/schedulers/gevent.html) — confirmed `GeventScheduler` in `apscheduler.schedulers.gevent`
- [APScheduler CronTrigger docs](https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html) — `CronTrigger.from_crontab()` for 5-field cron strings

### Secondary (MEDIUM confidence)
- [flask-apscheduler flask_context.py example](https://github.com/viniciuschiele/flask-apscheduler/blob/master/examples/flask_context.py) — Flask app context pattern for scheduled jobs (`with db.app.app_context():`)
- [APScheduler SQLAlchemyJobStore module](https://apscheduler.readthedocs.io/en/3.x/modules/jobstores/sqlalchemy.html) — jobstore configuration, tablename defaults to `apscheduler_jobs`
- [paho.mqtt.python matcher.py source](https://github.com/eclipse-paho/paho.mqtt.python/blob/master/src/paho/mqtt/matcher.py) — confirmed `iter_match`, `__setitem__`, `__getitem__`, `__delitem__` API

### Tertiary (LOW confidence)
- None — all claims above are verified against official sources or confirmed via local Python execution.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — APScheduler version confirmed on PyPI; paho-mqtt MQTTMatcher confirmed working locally; blinker/Flask-SQLAlchemy/deque all from project's installed dependencies
- Architecture: HIGH — patterns derived directly from official APScheduler docs, existing project code patterns, and confirmed library APIs
- Pitfalls: HIGH — GeventScheduler vs BackgroundScheduler verified in official docs; pickle limitation documented in APScheduler; loop prevention is a spec decision

**Research date:** 2026-03-24
**Valid until:** 2026-06-24 (APScheduler 3.x is stable; paho-mqtt 2.x API stable)
