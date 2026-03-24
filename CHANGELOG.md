# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-03-24

### Added

#### Automation Rules Engine
- **IF/THEN automation rules**: Create rules that evaluate conditions against incoming MQTT messages and fire actions automatically
- **11-operator condition evaluator**: eq, ne, gt, lt, gte, lte, contains, not_contains, regex, exists, not_exists
- **Compound conditions**: `all` (AND) and `any` (OR) for complex logic
- **JSON path support**: Dot-notation paths like `sensors.outdoor.temp` for nested payload fields
- **Action types**: Publish to topic, webhook HTTP POST, log to alert history
- **Loop detection**: `__source` marker prevents feedback loops, per-rule rate limiting (10/min default), global circuit breaker (100/min)
- **Time-based rules**: APScheduler with cron expressions (e.g., "every 5 minutes")
- **Hot-reload**: Rule changes take effect immediately without app restart
- **Dry-run testing**: Test rules against sample payloads before activating
- **Rules REST API**: Full CRUD at `/api/v1/rules/` with enable/disable and dry-run endpoints

#### Webhook Alerting
- **HTTP webhook delivery**: Configurable URL with customizable payload templates using `{{topic}}`, `{{payload}}`, `{{timestamp}}` variables
- **Retry with exponential backoff**: 3 retries at 1s, 5s, 25s on server errors
- **SSRF protection**: Blocks webhook URLs pointing to private/reserved addresses (RFC-1918, localhost, link-local)
- **Alert deduplication**: Configurable cooldown window (5 min default) prevents alert storms
- **Alert history**: Persistent record of all alerts with delivery status, viewable via API and UI

#### Modern Frontend
- **Alpine.js component architecture**: Reactive UI components replacing vanilla JS
- **htmx interactions**: Form submissions, CRUD operations, and pagination without full page reloads
- **Socket.IO batching**: Server-side 100ms batch window handles 1000+ msg/sec without browser flooding
- **Rules Editor UI**: Create, edit, delete, enable/disable, and dry-run test rules inline
- **Alert History panel**: Filterable by rule, severity, and time range with pagination
- **Tab navigation**: Dashboard / Rules / Alerts / Analytics / Plugins tabs

#### REST API & Authentication
- **Versioned API**: All endpoints under `/api/v1/` prefix with consistent JSON envelope responses
- **OpenAPI documentation**: Swagger UI at `/api/v1/docs` with full endpoint documentation
- **User authentication**: Flask-Login with username/password, session cookies
- **API tokens**: `X-API-Key` header for programmatic access, token CRUD endpoints
- **Rate limiting**: Configurable per-IP limit on publish endpoint (30/min default)
- **CORS support**: Cross-origin API access for external consumers
- **SECRET_KEY guard**: Application refuses to start with insecure key in production

#### Analytics & Observability
- **Per-topic analytics**: Message rate counters and numeric payload histograms
- **Analytics dashboard**: Real-time top-topics-by-rate widget with histogram drill-down
- **Structured logging**: structlog with JSON output (production) and colored console (development)
- **Prometheus metrics**: `/metrics` endpoint with message counters, rule firing rates, connection gauges
- **Topic favorites**: Star/bookmark topics for quick access
- **Retained message indicator**: Visual "R" badge on retained messages

#### Plugin Architecture
- **Plugin hook specification**: `MQTTUIPlugin` base class with `on_message`, `on_connect`, `on_rule_trigger` hooks via pluggy
- **Subprocess isolation**: Plugins run in separate processes with empty environment — no access to app, database, or MQTT client
- **Entry-point discovery**: Standard Python packaging via `importlib.metadata` entry_points
- **Plugin management UI**: View installed plugins, enable/disable via toggle
- **Bundled examples**: JSON Formatter and Topic Logger plugins included

### Changed

#### Architecture Overhaul
- **Flask application factory**: Monolithic `app.py` refactored into `mqttui/` package with blueprints
- **gevent async mode**: Replaced unmaintained eventlet with gevent for WebSocket support
- **paho-mqtt 2.x**: Upgraded to modern `CallbackAPIVersion.VERSION2` callback API
- **Flask 3.1.x**: Upgraded from Flask 2.0.1 with compatible Werkzeug
- **SQLite WAL mode**: Write-ahead logging with `busy_timeout` on all connections for concurrent access
- **Blinker event bus**: Internal signals (`mqtt_message_received`, `rule_fired`, `alert_triggered`) decouple all components
- **Python 3.11**: Docker base image upgraded from 3.9
- **Tailwind CSS v4**: Standalone CLI replacing CDN v2.x (no Node.js dependency)

#### Testing
- **218+ automated tests**: pytest infrastructure with shared fixtures across all 7 phases
- **Test categories**: App factory, database, routes, rules evaluator, rules engine, rules API, auth, API v1, webhook, cooldown, alerts API, frontend partials, analytics, observability, UX features, plugin registry, plugin runner, plugins API

### New Environment Variables
- `MQTTUI_ADMIN_USER`: Admin username (default: admin)
- `MQTTUI_ADMIN_PASSWORD`: Admin password (required for first run)
- `MQTTUI_RATE_LIMIT`: Publish rate limit (default: 30/minute)
- `SECRET_KEY`: Flask secret key (required in production, must not be "dev" or "change-me")

## [1.3.2] - 2025-08-24
### Added
- **Complete UI Redesign**: Collapsible sidebar layout for maximum screen real estate utilization
- **Advanced Search Panel**: Comprehensive message filtering with regex patterns, JSON path queries, content search, and time-based filters
- **Message Persistence**: SQLite database storage with automatic cleanup and configurable message limits
- **Filter Presets**: Save and load frequently used search filter combinations
- **Network Visualization Enhancements**:
  - Node pinning functionality (double-click to pin/unpin nodes, red color indicates pinned)
  - Improved physics engine with overlap prevention
  - Fullscreen support for Message Flow diagram
  - Right-click context menu for node management
- **Collapsible Sidebar**: Hide/show controls panel to maximize Message Flow and Messages viewing area
- **Enhanced API Endpoints**:
  - `/api/messages` with advanced filtering support
  - `/api/topics` with statistics
  - `/api/filter-presets` for preset management

### Changed
- **Layout Architecture**: Complete redesign from grid-based to flexbox sidebar layout
- **Message Flow Area**: Now takes up significantly more screen space (up to 100% width when sidebar hidden)
- **Message Rate Chart**: Moved to compact sidebar position for better space utilization
- **Topic Filtering**: Now actually filters displayed messages instead of just clearing the list
- **Advanced Search**: Collapsible panel, closed by default to reduce visual clutter
- **Screen Space Optimization**: Removed unnecessary padding, maximized content area utilization

### Fixed
- **Topic Dropdown Functionality**: Fixed issue where topic selection only cleared messages instead of filtering
- **Message Stacking**: Resolved overlapping div issue in the main content area
- **Layout Responsiveness**: Proper flexbox implementation ensures consistent 50/50 split between Message Flow and Messages
- **Database Thread Safety**: Implemented thread-local connections for concurrent message storage

### Technical Improvements
- **Database Schema**: Enhanced with indexes for better query performance
- **Message Filtering**: Support for regex topic patterns, JSON path queries, and content search
- **Network Physics**: Improved node positioning with `avoidOverlap` and better stabilization
- **JavaScript Architecture**: Modular functions for filter management and UI interactions
- **CSS Layout**: Modern flexbox implementation with smooth transitions and animations

## [1.3.1] - 2024-08-24
### Added
- LOG_LEVEL environment variable support for controlling application logging verbosity (#9)
- Topic subscription filtering via MQTT_TOPICS environment variable (#6)
- Multi-architecture Docker support (AMD64, ARM64, ARMv7) with new Dockerfile.multiarch (#3)
- GitHub Actions workflow for automated multi-platform Docker builds
- Enhanced documentation for MQTT broker address format (#7)
- Proper Flask-SocketIO server startup when running app.py directly (#12)

### Fixed
- MQTT v5 connection error by adding properties parameter to on_connect callback (#8)
- Application no longer exits prematurely when run outside Docker (#12)
- Improved LOG_LEVEL validation in entrypoint.sh with gunicorn support

### Changed
- Enhanced logging configuration with better formatting and level control
- Updated README with comprehensive configuration documentation
- Improved error handling for MQTT v5 connections

## [1.3.0] - 2024-08-27
### Added
- Improved logging for MQTT connection attempts and status
- Client ID specification for MQTT connection
- Support for different MQTT protocol versions

### Changed
- Modified app.py to ensure MQTT connection is attempted when run in a container
- Refactored server startup process for better compatibility with both development and production environments

### Fixed
- Resolved issues with MQTT connection not being established
- Fixed problems related to username/password authentication for MQTT brokers
- Improved error handling for non-UTF-8 encoded MQTT messages

## [1.2.0] - 2024-08-24
### Added
  - Debug Bar feature for enhanced developer insights
  - Real-time websocket connection/disconnect status
  - MQTT connection status and last message details
  - Request duration tracking
  - Toggle functionality to show/hide the Debug Bar

## [1.0.0] - 2024-08-19
### Added
- Initial release of MQTT Web Interface
- Real-time visualization of MQTT topic hierarchy and message flow
- Ability to publish messages to MQTT topics
- Display of message statistics (connection count, topic count, message count)
- Interactive network graph showing topic relationships
- Docker support for easy deployment
