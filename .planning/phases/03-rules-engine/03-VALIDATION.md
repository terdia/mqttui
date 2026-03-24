---
phase: 3
slug: rules-engine
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-24
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (confirmed in `tests/` directory with conftest.py) |
| **Config file** | pytest.ini |
| **Quick run command** | `pytest tests/test_rules_evaluator.py tests/test_rules_engine.py tests/test_rules_api.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_rules_evaluator.py tests/test_rules_engine.py tests/test_rules_api.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 3 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | RULE-01 | unit | `pytest tests/test_rules_evaluator.py -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | RULE-01 | unit | `pytest tests/test_rules_evaluator.py -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | RULE-02,03,04 | unit | `pytest tests/test_rules_engine.py -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | RULE-02,03,04,05 | unit | `pytest tests/test_rules_engine.py -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | RULE-08 | integration | `pytest tests/test_rules_api.py -x` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | RULE-05,08 | integration | `pytest tests/test_rules_api.py -x` | ❌ W0 | ⬜ pending |
| 03-04-01 | 04 | 3 | RULE-06 | unit | `pytest tests/test_rules_engine.py -x` | ❌ W0 | ⬜ pending |
| 03-04-02 | 04 | 3 | RULE-07 | integration | `pytest tests/test_rules_engine.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_rules_evaluator.py` — unit tests for condition evaluator (operators, compound, dot-path)
- [ ] `tests/test_rules_engine.py` — unit/integration tests for RuleEngine, rate limiter, loop prevention, hot-reload
- [ ] `tests/test_rules_api.py` — integration tests for REST CRUD, enable/disable, dry-run
- [ ] APScheduler install: `pip install "APScheduler[gevent,sqlalchemy]==3.11.2"` — added in plan 03-01

*Wave 0 test files are created by plan tasks themselves (test-inclusive plans).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rule fires on live MQTT message from broker | RULE-03 | Requires running MQTT broker | Publish via mosquitto_pub, verify rule fires in UI/logs |
| APScheduler job survives app restart | RULE-06 | Requires process restart cycle | Create time-based rule, restart app, verify job still runs |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 3s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-24
