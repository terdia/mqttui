# Phase 5: Frontend - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Modernize the frontend from single-file vanilla JS to Alpine.js + htmx component architecture on existing Jinja2 templates. Implement server-side Socket.IO message batching (100ms window), Rules Editor UI (create/edit/delete/dry-run), Alert History panel, and htmx for all non-real-time interactions. Upgrade to Tailwind CSS v4 standalone CLI.

</domain>

<decisions>
## Implementation Decisions

### Socket.IO Batching
- Server-side 100ms batch window using gevent timer
- Collect messages into buffer, emit as mqtt_messages_batch array every 100ms
- Client receives batch and appends all at once (single DOM update)
- Eliminates per-message emit that floods browser at >50 msg/sec

### Alpine.js Component Architecture
- Alpine.js 3.x loaded via CDN (no build pipeline)
- Components for: message list, rules editor, alert history, topic graph, stats
- x-data directives on HTML elements replace inline JS event handlers
- Alpine.store for shared state (connection status, selected topic, filters)

### htmx for Non-Real-Time
- htmx 2.x loaded via CDN
- Rule CRUD forms use hx-post/hx-put/hx-delete with hx-target for partial page updates
- Filter forms use hx-get for message search without full page reload
- Pagination uses hx-get with hx-push-url for browser history
- All htmx responses return HTML partials from Jinja2 templates

### Rules Editor UI
- Form-based rule creation: topic pattern, condition builder, action selector
- Condition builder: dropdown for operator, input for path and value
- Action selector: publish (topic + payload), webhook (URL + template), log (severity + message)
- Inline dry-run: button to test rule against recent messages, shows result
- Enable/disable toggle per rule
- Edit in-place, delete with confirmation

### Alert History Panel
- Dedicated panel/tab showing alert history from /api/v1/alerts
- Filterable by rule, severity, time range
- Shows: timestamp, rule name, action type, status (success/failed/suppressed), details

### Tailwind CSS v4
- Tailwind CSS v4 standalone CLI (no Node.js in production)
- Replaces CDN v2.x with locally compiled CSS
- Dark theme preserved, using v4 color system

### Claude's Discretion
- Exact Alpine.js component boundaries and naming
- Layout of rules editor (sidebar vs modal vs page)
- Alert history panel placement (tab vs collapsible section)
- Exact htmx partial template structure
- Whether to split script.js into multiple files or keep as single file with Alpine components
- Tailwind CSS v4 CLI integration into Docker build

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- templates/index.html — existing Jinja2 template (180 lines) with Tailwind dark theme
- static/script.js — existing vanilla JS (744 lines) with Socket.IO, Vis.js, Chart.js
- static/styles.css — custom CSS for scrollbar, debug bar, focus states
- templates/login.html — auth page template (47 lines)
- mqttui/routes/main.py — UI route handlers
- mqttui/routes/rules.py — rules API (CRUD, enable/disable, dry-run)
- mqttui/routes/alerts.py — alerts API (list with pagination)

### Established Patterns
- Jinja2 server-rendered templates with Tailwind utility classes
- Socket.IO client for real-time message streaming
- Vis.js for network graph visualization
- Chart.js for message rate chart
- Dark theme (bg-gray-900, bg-gray-800, text-white)

### Integration Points
- templates/index.html — main template needs Alpine.js + htmx integration
- static/script.js — needs refactor to Alpine.js components
- mqttui/routes/main.py — needs htmx partial template routes
- Socket.IO emit in mqtt_client.py — needs batching logic
- Docker build — needs Tailwind CLI step

</code_context>

<specifics>
## Specific Ideas

- Keep Vis.js and Chart.js as-is — they work well and don't need Alpine.js wrapping
- The Socket.IO batching MUST be server-side (not client-side) per research recommendations
- htmx partial templates should be in a templates/partials/ subdirectory

</specifics>

<deferred>
## Deferred Ideas

- Visual flow builder for rules — anti-feature per research (Node-RED does this better)
- Custom dashboard layout — Grafana exists, keep fixed layouts
- Mobile-specific responsive breakpoints — ensure responsive but don't optimize for mobile

</deferred>
