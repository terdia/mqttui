# Feature Research

**Domain:** MQTT Web Interface / IoT Dashboard with Automation
**Researched:** 2026-03-24
**Confidence:** HIGH (cross-referenced against MQTTX, ThingsBoard, Node-RED, EMQX, HiveMQ official docs and current sources)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that MQTT web interface users assume exist. Missing these makes the product feel incomplete or untrustworthy compared to free alternatives like MQTT Explorer.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Real-time message streaming | MQTT is a real-time protocol; batched/polled display is immediately frustrating | LOW | Already exists via Socket.IO |
| Topic tree / hierarchy view | MQTT topics are hierarchical; flat list is unusable beyond a few topics | MEDIUM | Already exists via Vis.js graph |
| Subscribe / unsubscribe controls | Users need to control which topics are active, not see everything always | LOW | Already exists |
| Publish message UI | Bidirectional — read-only view is a debug tool, not a control tool | LOW | Already exists |
| Message history with scroll | Users need to look back at what happened; ephemeral-only is a dealbreaker | LOW | Already exists via SQLite |
| Search and filter | High-throughput brokers produce too much data; filter by topic/payload/time is essential | MEDIUM | Already exists (regex, JSON path, time range) |
| Connection status indicator | Users must know if the broker connection is live or broken at a glance | LOW | Already exists via debug bar |
| MQTT v3.1.1 and v5 support | The two dominant versions are both in active use in production | MEDIUM | Already exists |
| QoS level display and setting | QoS 0/1/2 affects delivery guarantees; users need to see and set it | LOW | Partial — display exists; verify publish controls |
| Retained message indicator | Retained messages behave differently; users must know which they are | LOW | Not confirmed as existing; needs implementation |
| TLS/SSL connection support | Production brokers require encrypted connections | MEDIUM | Must verify — likely via env var passthrough |
| Dark / light theme | Developer tooling without dark mode draws immediate complaints | LOW | Already exists (dark theme) |
| Docker deployment | Self-hosted tools must be easy to deploy; Docker is the baseline expectation | LOW | Already exists |
| Configurable broker connection | Hard-coded broker URL is unusable; env vars or UI config needed | LOW | Already exists via 15+ env vars |
| Message rate / throughput display | Users debug performance issues; a messages/sec indicator is standard | LOW | Already exists via Chart.js |

### Differentiators (Competitive Advantage)

Features that elevate mqttui beyond a passive viewer into an intelligent control plane. These align with the core value: "the app should not just display messages but act on them."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Automation rules engine (IF topic/payload THEN action) | Turns passive monitoring into active control; no competing open-source MQTT web UI does this well in-browser | HIGH | Core milestone goal. Pattern: trigger (topic + payload condition) + action (publish, webhook, alert). EMQX/ThingsBoard rule engines are the reference implementations |
| Message transformation pipelines | Allows reshaping/enriching payloads before re-publishing; essential for protocol bridging and data normalization | HIGH | JSONata is the strongest transformation language for JSON; existing search already uses JSON path, so users understand the paradigm |
| Real-time alerting with webhooks | Notify external systems (Slack, PagerDuty, HTTP endpoints) when conditions are met; closes the last-mile between monitoring and response | MEDIUM | ThingsBoard, EMQX both offer this as a first-class feature. HTTP POST with configurable payload template is the minimum viable form |
| Plugin / extension architecture | Community contributions and custom integrations without forking; multiplies the surface area of use cases | HIGH | Python entry-point pattern (importlib + defined interface contract) is the right approach for a Flask/Python backend |
| Per-topic analytics and statistics | Message rate per topic, payload size distribution, value histograms for numeric payloads — beyond just global message rate | MEDIUM | Competitors like MQTT Explorer offer numeric topic charting; ThingsBoard has full telemetry widgets. Currently only global rate exists |
| Enhanced message analytics dashboard | Time-series charts for selected topics, aggregate stats (min/max/avg for numeric payloads), anomaly highlighting | MEDIUM | Requires time-series query layer over SQLite; low overhead to add given existing message persistence |
| Filter presets and saved views | Users repeat the same debugging workflows; named presets save significant time | LOW | Already exists — this is already a differentiator vs MQTT Explorer/basic clients |
| REST API (formalized, documented) | Programmatic access enables CI/CD integration, scripting, and third-party dashboards consuming mqttui data | MEDIUM | OpenAPI/Swagger spec + versioned routes. Needed before plugin architecture lands |
| Structured logging and observability | Operators need to debug production issues; stdout JSON logs + /metrics endpoint enable integration with Datadog, Prometheus | MEDIUM | Pain point identified in PROJECT.md; competitors don't surface this well |
| User authentication (basic, per-install) | Multi-user households, shared team deployments, and any internet-exposed install need login | MEDIUM | Username/password per install with JWT sessions. NOT multi-tenant — single install, few users |
| Message transformation preview / dry-run | Rules and transformations are risky to test in production; a sandbox that shows output for a sample payload removes fear | MEDIUM | Critical for adoption of the rules engine — without it users won't trust writing rules |
| Topic favorites / bookmarks | Power users monitor specific topics repeatedly; bookmarks surface them instantly without re-filtering | LOW | Trivial to implement but meaningfully improves daily-use DX |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Visual flow builder (Node-RED style drag-and-drop) | "Rules should be visual" — users see Node-RED and want the same | Enormous frontend complexity, requires canvas UI framework, infinite edge cases in wiring logic; Node-RED already exists and does this better | Use structured form-based rule creation with WHEN/THEN fields — 90% of use cases covered, 10% of the implementation complexity |
| Multi-broker management | "I have 3 brokers" — natural feature request for power users | Session management, connection pooling, and UI complexity multiply; data model changes cascade everywhere | Defer to v2. Single broker with clean connection switching is sufficient for v1.5 |
| Message replay / time travel | "Play back a sequence of messages" — useful for debugging | Requires time-ordered replay engine, clock simulation, and careful ordering guarantees with SQLite | Defer: search + filter + time range covers 80% of the replay use case without the complexity |
| Custom widget drag-and-drop dashboard | "I want a Grafana-like layout" — users want to arrange charts | Full dashboard layout engine is a product in itself; Grafana and ThingsBoard already do this | Provide well-designed fixed analytics views that cover the most important metrics; defer custom layout |
| Enterprise SSO / SAML / LDAP | "My org requires it" — security teams ask for this | Complexity out of scope for self-hosted single-install tool; adds external service dependencies | Basic auth + API tokens is sufficient for v2. Document SSO as v3 |
| Mobile native app | IoT operators want phone alerts | Out of scope and a separate product; responsive web covers 80% of mobile use cases | Ensure responsive design works on mobile browsers; push alerts via webhooks to existing mobile notification services (e.g., PushOver, Ntfy) |
| Built-in MQTT broker | "I want an all-in-one tool" | Broker implementation is a separate domain; Mosquitto, EMQX, HiveMQ are mature and well-maintained | Document Mosquitto + mqttui as the recommended self-hosted stack; provide docker-compose example |
| AI/LLM payload analysis | MQTTX now has Copilot — "AI should explain my payloads" | Requires LLM API keys, external dependency, privacy concerns for production data; adds latency | Phase this carefully as optional/opt-in if at all; do not make it a core dependency |

---

## Feature Dependencies

```
[Automation Rules Engine]
    └──requires──> [REST API (formalized)]
    └──requires──> [User Authentication]
                       └──enhances──> [Plugin Architecture]

[Message Transformation Pipelines]
    └──requires──> [Automation Rules Engine] (transformations are actions within rules)
    └──requires──> [Message Transformation Preview / Dry-run]

[Real-time Alerting + Webhooks]
    └──requires──> [Automation Rules Engine] (alerts are triggered by rules)

[Plugin Architecture]
    └──requires──> [REST API (formalized)] (plugins consume and expose API endpoints)
    └──requires──> [Automation Rules Engine] (plugins can define rule action types)

[Per-topic Analytics]
    └──requires──> [Enhanced Message Analytics Dashboard] (analytics feeds the dashboard)
    └──enhances──> [Automation Rules Engine] (analytics data can trigger rules)

[User Authentication]
    └──enhances──> [REST API (formalized)] (API tokens tied to user accounts)

[Message Transformation Preview]
    └──requires──> [Message Transformation Pipelines]

[Structured Logging / Observability]
    ──independent──> (no dependencies, can ship any time)

[Topic Favorites / Bookmarks]
    ──independent──> (no dependencies, low-hanging fruit)

[Retained Message Indicator]
    ──independent──> (cosmetic display flag, no dependencies)
```

### Dependency Notes

- **Automation Rules Engine requires REST API:** Rules need to be created, updated, deleted, and queried via API so the frontend can manage them without page reloads. Without a clean REST API, rules become ad-hoc backend state.
- **Message Transformation requires Rules Engine:** Transformations are not standalone — they are actions attached to rule triggers. Building them before the rules engine means re-architecting later.
- **Real-time Alerting requires Rules Engine:** Alerts are the output side of a rule. The alerting delivery system (HTTP POST, webhook) should be built as a rule action type, not a separate subsystem.
- **Plugin Architecture requires REST API:** Plugins that expose new endpoints or new rule action types must integrate with the existing API surface cleanly. REST API formalization creates the stable contract plugins depend on.
- **Message Transformation Preview enhances adoption:** Without a dry-run sandbox, users will avoid writing transformation rules out of fear of breaking production message flows. This is a safety valve that gates adoption of the transformation feature.

---

## MVP Definition

This is a milestone project (v2.0), not a greenfield MVP. The existing product already covers table stakes. The milestone MVP is the minimum set of *new* features that delivers the "automation/agency" value proposition.

### Launch With (milestone v2.0 core)

- [ ] **Automation Rules Engine (basic)** — IF (topic matches + payload condition) THEN (publish to topic OR trigger webhook). This is the core differentiator and the reason for the milestone. Even a simple version makes mqttui categorically different from all competing MQTT web UIs.
- [ ] **REST API formalization** — OpenAPI-documented versioned routes. Required foundation for rules engine frontend, plugin system, and external integrations.
- [ ] **Real-time alerting via webhooks** — HTTP POST to configurable URL when a rule fires. Closes the monitoring-to-response loop that is the most immediate user pain point.
- [ ] **User authentication (basic)** — Username/password login with session tokens. Any internet-exposed deployment without auth is a security liability; this gates everything else.
- [ ] **Message Transformation Preview / Dry-run** — Sandbox for testing transformation expressions against a sample payload. Unblocks user adoption of transformations.
- [ ] **Modern frontend component architecture** — Refactor the 744-line single-file vanilla JS into component-based structure (React or Vue). Required to build the rules engine UI and analytics dashboard without turning the codebase into unmaintainable spaghetti.

### Add After Validation (v2.x)

- [ ] **Message transformation pipelines** — Add once rules engine is proven stable and users are asking for payload reshaping. Trigger: users filing issues asking "can I transform the payload before republishing?"
- [ ] **Per-topic analytics and statistics** — Add when users start requesting "how often does topic X fire?" and "what are the value ranges?" Trigger: dashboard usage data showing users spending time on the message rate chart.
- [ ] **Plugin / extension architecture** — Add once REST API is stable and there are 2-3 concrete use cases that can't be met without it. Trigger: community requests for custom rule action types or custom data sources.
- [ ] **Structured logging and Prometheus metrics export** — Add when operators start deploying at scale and need observability. Trigger: GitHub issues about debugging production deployments.
- [ ] **Topic favorites / bookmarks** — Low-effort quality-of-life improvement, add any time after core features land.

### Future Consideration (v3+)

- [ ] **Multi-broker management** — Only after single-broker experience is excellent and there's demonstrated demand. Why defer: data model changes are significant.
- [ ] **Enterprise SSO/SAML** — Only when enterprise customers are paying. Why defer: significant complexity, external service dependencies.
- [ ] **Message replay / time travel** — Only after analytics dashboard validates that users want time-ordered playback, not just search. Why defer: ordering guarantees and replay engine are complex.
- [ ] **Custom dashboard layout (drag-and-drop)** — Only if analytics usage shows users want personalization. Why defer: full layout engine is a product in itself.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Automation Rules Engine (basic) | HIGH | HIGH | P1 |
| REST API formalization | HIGH | MEDIUM | P1 |
| User Authentication (basic) | HIGH | MEDIUM | P1 |
| Real-time Alerting / Webhooks | HIGH | MEDIUM | P1 |
| Modern Frontend Architecture | HIGH | HIGH | P1 |
| Message Transformation Preview | HIGH | MEDIUM | P1 |
| Message Transformation Pipelines | HIGH | HIGH | P2 |
| Per-topic Analytics | MEDIUM | MEDIUM | P2 |
| Structured Logging / Observability | MEDIUM | LOW | P2 |
| Plugin Architecture | MEDIUM | HIGH | P2 |
| Topic Favorites / Bookmarks | MEDIUM | LOW | P2 |
| Retained Message Indicator | LOW | LOW | P3 |
| Enhanced Analytics Dashboard | MEDIUM | MEDIUM | P3 |
| Multi-broker Management | MEDIUM | HIGH | P3 |
| Message Replay / Time Travel | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for v2.0 launch — defines the milestone
- P2: Should have, add in v2.x iterations after v2.0 lands
- P3: Nice to have, future milestone consideration

---

## Competitor Feature Analysis

| Feature | MQTT Explorer | MQTTX | Node-RED | ThingsBoard | Our Approach |
|---------|---------------|-------|----------|-------------|--------------|
| Real-time message stream | Yes | Yes | Yes | Yes | Existing (Socket.IO) |
| Topic hierarchy view | Yes (tree) | Yes (tree) | No | Yes (assets) | Existing (network graph — unique visual) |
| Publish UI | Yes | Yes | Yes | Yes | Existing |
| Message history / search | Basic | Basic | No (stateless) | Yes (telemetry) | Existing (SQLite + regex + JSON path — stronger than MQTTX) |
| Automation rules engine | No | No | Yes (visual flows) | Yes (rule chains) | Build: form-based IF/THEN rules, simpler than Node-RED, more accessible than ThingsBoard |
| Message transformation | No | Script only | Yes (function nodes) | Yes (TBEL scripting) | Build: JSONata expressions in rule actions |
| Alerting / webhooks | No | No | Yes (via HTTP nodes) | Yes (notifications center) | Build: webhook action type on rule engine |
| Plugin architecture | No | No | Yes (npm packages) | Yes (custom modules) | Build: Python entry-point pattern |
| Analytics dashboard | Numeric charts per topic | None | None (separate dashboard tools) | Full telemetry widgets | Build: per-topic time series and stats, scoped narrower than ThingsBoard |
| User authentication | No | No | Basic (optional) | Yes (multi-tenant) | Build: single-install basic auth |
| REST API | No | No | Yes | Yes | Build: OpenAPI-documented versioned routes |
| AI/LLM features | No | Yes (Copilot 2.0, MCP) | No | No | Optional/deferred — MQTTX owns this space for client tooling |
| Docker deployment | No | Yes (web version) | Yes | Yes | Existing |

---

## Sources

- [Top 7 MQTT Client Tools for Developers in 2025 — EMQ](https://www.emqx.com/en/blog/mqtt-client-tools)
- [ThingsBoard Rule Engine Overview](https://thingsboard.io/docs/user-guide/rule-engine-2-0/overview/)
- [ThingsBoard Notification Center](https://thingsboard.io/docs/user-guide/notifications/)
- [EMQX Rule Engine Documentation](https://docs.emqx.com/en/emqx/latest/data-integration/rules.html)
- [EMQX Webhook Integration](https://docs.emqx.com/en/emqx/latest/data-integration/webhook.html)
- [MQTT Explorer](http://mqtt-explorer.com/)
- [MQTTX Copilot Documentation](https://mqttx.app/docs/copilot)
- [MQTTX 1.12.0 Release Notes — Copilot 2.0 + MCP](https://www.emqx.com/en/blog/mqttx-1-12-0-release-notes)
- [Node-RED — Working with MQTT (FlowFuse)](https://flowfuse.com/blog/2024/06/how-to-use-mqtt-in-node-red/)
- [Condition-Action Rules Engines for IoT — IoT For All](https://www.iotforall.com/condition-action-rules-engines-iot)
- [HiveMQ RBAC for Control Center](https://www.hivemq.com/blog/rbac-for-the-control-center-with-ese/)
- [MQTT to Webhook — EMQ](https://www.emqx.com/en/blog/mqtt-to-webhook)
- [Flask Extension Development — Official Flask Docs](https://flask.palletsprojects.com/en/stable/extensiondev/)
- [JSONata in Node-RED — Totally Information](https://totallyinformation.github.io/nr-qa/jsonata.html)

---
*Feature research for: MQTT Web Interface / IoT Dashboard with Automation*
*Researched: 2026-03-24*
