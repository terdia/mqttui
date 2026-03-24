"""RuleEngine -- runtime heart of the rules automation system.

Subscribes to mqtt_message_received events, evaluates matching rules,
executes actions, and enforces safety mechanisms (loop prevention,
per-rule rate limiting, global circuit breaker).

Also manages time-based rules via APScheduler and hot-reloads rule cache
when rules are created, updated, or deleted.
"""
import json
import logging
import time
from collections import deque
from datetime import datetime

from paho.mqtt.matcher import MQTTMatcher

from mqttui.events import mqtt_message_received, rule_fired, rule_changed
from mqttui.rules.evaluator import evaluate, ConditionError
from mqttui.rules.actions import execute_action

logger = logging.getLogger(__name__)

# Module-level singleton reference for APScheduler pickle compatibility
_engine = None


def _fire_scheduled_rule(app, rule_id):
    """Module-level function for APScheduler pickle compatibility.

    APScheduler serialises job targets; lambdas and bound methods cannot be
    pickled, so we use a plain module-level function with explicit args.
    """
    with app.app_context():
        if _engine:
            _engine.fire_scheduled_rule(rule_id)


def get_engine():
    """Return the module-level RuleEngine singleton (or None)."""
    return _engine


class RuleEngine:
    """Evaluate automation rules against live MQTT messages.

    Attributes:
        _rules: dict mapping rule_id -> Rule ORM instance (enabled only)
        _matcher: MQTTMatcher mapping subscription patterns to rule_ids
        _rule_timestamps: dict mapping rule_id -> deque of firing timestamps
        _global_timestamps: deque of all firing timestamps (circuit breaker)
        _GLOBAL_LIMIT: max total firings per window (default 100)
        _WINDOW: sliding window duration in seconds (default 60)
        _scheduler: GeventScheduler instance (or None before init_scheduler)
    """

    def __init__(self, app=None):
        self._rules = {}
        self._matcher = MQTTMatcher()
        self._rule_timestamps = {}
        self._global_timestamps = deque()
        self._GLOBAL_LIMIT = 100
        self._WINDOW = 60.0
        self._app = app
        self._scheduler = None

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def init_scheduler(self):
        """Start the APScheduler GeventScheduler with SQLAlchemy job store."""
        from apscheduler.schedulers.gevent import GeventScheduler
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

        uri = self._app.config['SQLALCHEMY_DATABASE_URI']
        self._scheduler = GeventScheduler(
            jobstores={'default': SQLAlchemyJobStore(url=uri)},
            job_defaults={
                'misfire_grace_time': 30,
                'max_instances': 1,
                'coalesce': True,
            },
        )
        self._scheduler.start()
        logger.info("APScheduler GeventScheduler started")

    def fire_scheduled_rule(self, rule_id):
        """Execute a time-based rule by id (called from scheduler job)."""
        rule = self._rules.get(rule_id)
        if rule is None or not rule.enabled:
            logger.debug(f"Scheduled rule {rule_id} skipped (not found or disabled)")
            return

        # Rate limit check
        if not self._check_rate_limit(rule):
            logger.debug(f"Scheduled rule {rule_id} rate-limited")
            return

        # Build action and context
        try:
            action_dict = json.loads(rule.action_json) if rule.action_json else {}
        except json.JSONDecodeError:
            logger.error(f"Invalid action JSON for scheduled rule {rule_id}")
            return

        context = {
            'rule_id': rule.id,
            'rule_name': rule.name,
            'topic': '__scheduled__',
            'payload': '',
        }

        try:
            result = execute_action(action_dict, context)
            if not result.get('success'):
                logger.warning(f"Scheduled action failed for rule {rule_id}: {result.get('detail')}")
        except Exception as e:
            logger.error(f"Scheduled action error for rule {rule_id}: {e}")
            return

        # Update rule stats
        try:
            from mqttui.extensions import sa
            rule.fire_count = (rule.fire_count or 0) + 1
            rule.last_fired = datetime.utcnow()
            sa.session.commit()
        except Exception as e:
            logger.error(f"Failed to update stats for scheduled rule {rule_id}: {e}")

        # Fire signal
        rule_fired.send(
            self,
            rule_id=rule.id,
            rule_name=rule.name,
            topic='__scheduled__',
            payload='',
        )

    def sync_scheduled_jobs(self):
        """Synchronise APScheduler jobs with the current rule cache.

        - New cron rules get jobs added.
        - Deleted rules get jobs removed.
        - Changed cron expressions are updated (replace_existing=True).
        """
        if self._scheduler is None:
            return

        from apscheduler.triggers.cron import CronTrigger

        existing_jobs = {job.id for job in self._scheduler.get_jobs()}

        for rule in self._rules.values():
            job_id = f'rule_{rule.id}'
            if rule.schedule_cron and rule.schedule_cron.strip():
                self._scheduler.add_job(
                    _fire_scheduled_rule,
                    trigger=CronTrigger.from_crontab(rule.schedule_cron),
                    args=[self._app, rule.id],
                    id=job_id,
                    replace_existing=True,
                )
                existing_jobs.discard(job_id)
            else:
                # Rule has no cron -- remove stale job if present
                if job_id in existing_jobs:
                    self._scheduler.remove_job(job_id)
                    existing_jobs.discard(job_id)

        # Cleanup jobs for rules that were deleted
        for job_id in existing_jobs:
            if job_id.startswith('rule_'):
                self._scheduler.remove_job(job_id)

        logger.debug("Scheduler jobs synced with rule cache")

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def reload_cache(self):
        """Load enabled rules from DB into in-memory cache and rebuild matcher."""
        from mqttui.rules.models import Rule

        ctx = self._app.app_context() if self._app else _nullcontext()
        with ctx:
            enabled_rules = Rule.query.filter_by(enabled=True).all()

            new_rules = {}
            new_matcher = MQTTMatcher()

            for rule in enabled_rules:
                new_rules[rule.id] = rule
                # MQTTMatcher stores value at subscription key
                # Multiple rules can share a topic, so store list
                try:
                    existing = new_matcher[rule.trigger_topic]
                    existing.append(rule.id)
                except KeyError:
                    new_matcher[rule.trigger_topic] = [rule.id]

            # Atomic swap
            self._rules = new_rules
            self._matcher = new_matcher

            # Clean stale rate-limit entries
            active_ids = set(new_rules.keys())
            stale_ids = set(self._rule_timestamps.keys()) - active_ids
            for rid in stale_ids:
                del self._rule_timestamps[rid]

        logger.info(f"RuleEngine cache reloaded: {len(new_rules)} enabled rules")

        # Sync scheduler jobs after cache reload
        self.sync_scheduled_jobs()

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _check_rate_limit(self, rule):
        """Check per-rule and global rate limits using sliding window.

        Returns True if the rule is allowed to fire, False if blocked.
        On allow, records the timestamp in both deques.
        """
        now = time.monotonic()
        cutoff = now - self._WINDOW

        # --- Global circuit breaker ---
        while self._global_timestamps and self._global_timestamps[0] < cutoff:
            self._global_timestamps.popleft()
        if len(self._global_timestamps) >= self._GLOBAL_LIMIT:
            logger.warning("Global circuit breaker triggered")
            return False

        # --- Per-rule rate limit ---
        if rule.id not in self._rule_timestamps:
            self._rule_timestamps[rule.id] = deque()
        rule_deque = self._rule_timestamps[rule.id]
        while rule_deque and rule_deque[0] < cutoff:
            rule_deque.popleft()
        if len(rule_deque) >= rule.rate_limit_per_min:
            logger.debug(f"Rate limit hit for rule {rule.id} ({rule.name})")
            return False

        # Allowed -- record timestamp
        rule_deque.append(now)
        self._global_timestamps.append(now)
        return True

    # ------------------------------------------------------------------
    # MQTT message handler
    # ------------------------------------------------------------------

    def on_mqtt_message(self, sender, **kwargs):
        """Handle an incoming MQTT message from the event bus.

        1. Parse payload, check for loop marker
        2. Match topic against cached rules
        3. For each match: check rate limit, evaluate condition, execute action
        4. Fire rule_fired signal on success
        """
        topic = kwargs.get('topic', '')
        payload_raw = kwargs.get('payload', '')

        # Parse payload
        try:
            payload_dict = json.loads(payload_raw)
        except (json.JSONDecodeError, TypeError):
            payload_dict = {}

        # Loop prevention: skip messages from our own automation
        if isinstance(payload_dict, dict) and payload_dict.get('__source') == 'mqttui-automation':
            logger.debug(f"Skipping automation message on {topic}")
            return

        # Find matching rules via MQTTMatcher
        matched_rule_ids = []
        try:
            for rule_id_list in self._matcher.iter_match(topic):
                if isinstance(rule_id_list, list):
                    matched_rule_ids.extend(rule_id_list)
                else:
                    matched_rule_ids.append(rule_id_list)
        except (StopIteration, KeyError):
            return

        if not matched_rule_ids:
            return

        ctx = self._app.app_context() if self._app else _nullcontext()
        with ctx:
            for rule_id in matched_rule_ids:
                rule = self._rules.get(rule_id)
                if rule is None:
                    continue

                # Rate limit check
                if not self._check_rate_limit(rule):
                    continue

                # Evaluate condition
                try:
                    condition = json.loads(rule.condition_json) if rule.condition_json else {}
                except json.JSONDecodeError:
                    logger.error(f"Invalid condition JSON for rule {rule.id}")
                    continue

                try:
                    if not evaluate(condition, payload_dict):
                        # Condition did not match -- undo rate limit recording
                        if rule.id in self._rule_timestamps and self._rule_timestamps[rule.id]:
                            self._rule_timestamps[rule.id].pop()
                        if self._global_timestamps:
                            self._global_timestamps.pop()
                        continue
                except ConditionError as e:
                    logger.error(f"Condition error for rule {rule.id}: {e}")
                    continue

                # Execute action
                try:
                    action = json.loads(rule.action_json) if rule.action_json else {}
                except json.JSONDecodeError:
                    logger.error(f"Invalid action JSON for rule {rule.id}")
                    continue

                context = {
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'topic': topic,
                    'payload': payload_raw,
                }

                try:
                    result = execute_action(action, context)
                    if not result.get('success'):
                        logger.warning(f"Action failed for rule {rule.id}: {result.get('detail')}")
                except Exception as e:
                    logger.error(f"Action execution error for rule {rule.id}: {e}")
                    continue

                # Update rule stats
                try:
                    from mqttui.extensions import sa
                    rule.fire_count = (rule.fire_count or 0) + 1
                    rule.last_fired = datetime.utcnow()
                    sa.session.commit()
                except Exception as e:
                    logger.error(f"Failed to update rule stats for {rule.id}: {e}")

                # Fire signal
                rule_fired.send(
                    self,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    topic=topic,
                    payload=payload_raw,
                )

    # ------------------------------------------------------------------
    # Hot-reload
    # ------------------------------------------------------------------

    def _on_rule_changed(self, sender, **kwargs):
        """Handle rule_changed signal by reloading the cache."""
        logger.info(f"Rule changed ({kwargs.get('action', 'unknown')}), reloading cache")
        self.reload_cache()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self):
        """Connect to the event bus, load rule cache, and start scheduler."""
        global _engine
        _engine = self

        mqtt_message_received.connect(self.on_mqtt_message)
        rule_changed.connect(self._on_rule_changed)
        self.reload_cache()

        if self._scheduler is None:
            self.init_scheduler()

        logger.info("RuleEngine connected to event bus")

    def disconnect(self):
        """Disconnect from the event bus and shut down scheduler."""
        mqtt_message_received.disconnect(self.on_mqtt_message)
        try:
            rule_changed.disconnect(self._on_rule_changed)
        except Exception:
            pass  # May not be connected
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        logger.info("RuleEngine disconnected from event bus")


class _nullcontext:
    """Minimal context manager for when no app context is needed."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
