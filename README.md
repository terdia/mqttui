# MQTTUI — Intelligent MQTT Web Interface

An open-source web application that monitors, visualizes, and **automates** your MQTT infrastructure. Create automation rules, get webhook alerts, track per-topic analytics, and extend with plugins — all from a single interface.

![Message Flow Screenshot](static/screenshot.png)

## What's New in v2.1

- **Multi-Broker Support** — Connect to multiple MQTT brokers simultaneously, manage from the Brokers tab, filter messages by broker
- **Telegram & Slack Alerts** — First-class action types in the rules editor, no raw webhook URLs needed

## What's New in v2.0

- **Automation Rules Engine** — Create IF/THEN rules: when a topic matches a pattern and payload meets a condition, automatically publish, fire a webhook, or log an alert
- **Alerting** — Telegram, Slack, and HTTP webhook notifications with retry/backoff, SSRF protection, and alert deduplication
- **Modern UI** — Alpine.js + htmx component architecture with tabbed navigation (Dashboard / Rules / Alerts / Analytics / Plugins / Brokers)
- **REST API** — Versioned `/api/v1/` endpoints with OpenAPI docs at `/api/v1/docs`
- **User Authentication** — Login with username/password, API tokens for programmatic access
- **Analytics** — Per-topic message rates, payload histograms, Prometheus `/metrics` endpoint
- **Plugin Architecture** — Extend with custom handlers running in subprocess isolation
- **218+ Automated Tests** — Full pytest suite across all features

## Features

### Core
- **Multi-broker** — connect to multiple MQTT brokers simultaneously, filter messages by broker
- Real-time MQTT message streaming via Socket.IO (handles 1000+ msg/sec with server-side batching)
- Interactive topic hierarchy network graph (Vis.js)
- Publish messages to any topic
- SQLite message persistence with advanced search (regex, JSON path, time range)
- Filter presets — save and load search combinations
- MQTT v3.1.1 and v5 protocol support
- Docker deployment with multi-arch support (AMD64, ARM64, ARMv7)

### Automation
- **Rules Engine**: 11 condition operators (eq, gt, contains, regex, exists, etc.) with compound all/any logic
- **JSON Path Conditions**: Match nested payload fields like `sensors.outdoor.temp > 30`
- **Actions**: Publish to topic, HTTP webhook, log alert
- **Loop Detection**: `__source` marker + per-rule rate limiting + global circuit breaker
- **Time-Based Rules**: Cron schedules via APScheduler (e.g., publish heartbeat every 5 minutes)
- **Dry-Run Testing**: Test rules against sample payloads before activating
- **Hot-Reload**: Rule changes take effect immediately, no restart needed

### Alerting & Notifications
- **Telegram**: Enter bot token + chat ID — get alerts directly in Telegram
- **Slack**: Enter incoming webhook URL — get alerts in your Slack channel
- **HTTP Webhooks**: Generic webhook with customizable payload templates (`{{topic}}`, `{{payload}}`, `{{timestamp}}`)
- Retry with exponential backoff (1s / 5s / 25s) on server errors
- SSRF protection — blocks private/reserved addresses
- Alert deduplication with configurable cooldown (5 min default)
- Persistent alert history with delivery status tracking

### Analytics & Observability
- Per-topic message rate counters and numeric payload histograms
- Structured JSON logging (structlog) for production
- Prometheus-compatible `/metrics` endpoint
- Topic favorites/bookmarks for quick access
- Retained message indicator

### Plugin System
- `MQTTUIPlugin` base class with `on_message`, `on_connect`, `on_rule_trigger` hooks
- Subprocess isolation — plugins cannot access app internals
- Python entry-point discovery (`pip install` your plugin)
- Management UI with enable/disable toggles
- Bundled examples: JSON Formatter, Topic Logger

## Quick Start

### Docker Compose (Recommended)

```bash
git clone https://github.com/terdia/mqttui.git
cd mqttui
docker compose up -d
```

This starts:
- Mosquitto MQTT broker on port 1883
- MQTTUI on port 8088

Open `http://localhost:8088` and log in with the admin credentials you set.

### Docker

```bash
docker pull terdia07/mqttui:v2.0
docker run -p 8088:5000 \
  -e MQTT_BROKER=your_broker \
  -e MQTTUI_ADMIN_USER=admin \
  -e MQTTUI_ADMIN_PASSWORD=changeme \
  -e SECRET_KEY=your-secret-key \
  terdia07/mqttui:v2.0
```

### Manual Installation

```bash
git clone https://github.com/terdia/mqttui.git
cd mqttui
pip install -r requirements.txt

# Set required environment variables
export MQTTUI_ADMIN_USER=admin
export MQTTUI_ADMIN_PASSWORD=changeme
export SECRET_KEY=your-secret-key
export MQTT_BROKER=localhost

python wsgi.py
```

### Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -q
```

### Demo Data

Populate realistic test data across all features (requires Docker Compose running):

```bash
./demo.sh
```

This creates 200+ messages, 4 automation rules, triggers alerts, sets up filter presets, and bookmarks topics. Great for evaluating all tabs and features.

## Configuration

### Required Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MQTTUI_ADMIN_USER` | Admin username | `admin` |
| `MQTTUI_ADMIN_PASSWORD` | Admin password | *(required)* |
| `SECRET_KEY` | Flask secret key (must not be "dev" in production) | *(required)* |

### MQTT Connection

| Variable | Description | Default |
|----------|-------------|---------|
| `MQTT_BROKER` | Broker address (IP or hostname, no protocol prefix) | `localhost` |
| `MQTT_PORT` | Broker port | `1883` |
| `MQTT_USERNAME` | Broker username | *(optional)* |
| `MQTT_PASSWORD` | Broker password | *(optional)* |
| `MQTT_KEEPALIVE` | Keep-alive interval (seconds) | `60` |
| `MQTT_VERSION` | Protocol version (`3.1.1` or `5`) | `3.1.1` |
| `MQTT_TOPICS` | Topics to subscribe (comma-separated) | `#` |

### TLS/SSL (MQTTS)

| Variable | Description | Default |
|----------|-------------|---------|
| `MQTT_TLS` | Enable TLS connection | `false` |
| `MQTT_TLS_CA_CERTS` | Path to CA certificate file | *(optional)* |
| `MQTT_TLS_CERTFILE` | Path to client certificate | *(optional)* |
| `MQTT_TLS_KEYFILE` | Path to client private key | *(optional)* |
| `MQTT_TLS_INSECURE` | Skip certificate verification (not recommended) | `false` |

**Example — connect to a TLS broker:**
```bash
docker run -p 8088:5000 \
  -e MQTT_BROKER=broker.hivemq.com \
  -e MQTT_PORT=8883 \
  -e MQTT_TLS=true \
  terdia07/mqttui:v2.0.0
```

### Application

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable development mode | `False` |
| `PORT` | Application port | `5000` |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
| `MQTTUI_RATE_LIMIT` | Publish endpoint rate limit | `30/minute` |

### Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_ENABLED` | Enable message persistence | `True` |
| `DB_PATH` | SQLite database path | `./data/mqtt_messages.db` |
| `DB_MAX_MESSAGES` | Max stored messages | `10000` |
| `DB_CLEANUP_DAYS` | Auto-delete messages older than X days | `30` |

## API Documentation

All API endpoints are under `/api/v1/` with OpenAPI documentation at `/api/v1/docs`.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/messages` | Message history with filtering |
| `POST` | `/api/v1/publish` | Publish MQTT message |
| `GET` | `/api/v1/topics` | Topic list with stats |
| `GET/POST` | `/api/v1/rules/` | List / create automation rules |
| `PUT/DELETE` | `/api/v1/rules/<id>` | Update / delete rule |
| `POST` | `/api/v1/rules/<id>/test` | Dry-run test a rule |
| `POST` | `/api/v1/rules/<id>/enable` | Enable rule |
| `GET` | `/api/v1/alerts/` | Alert history |
| `GET` | `/api/v1/analytics/topics` | Per-topic analytics |
| `GET` | `/api/v1/plugins/` | List plugins |
| `GET` | `/metrics` | Prometheus metrics |

All data endpoints require authentication (session cookie or `X-API-Key` header).

## Tech Stack

- **Backend**: Python 3.11, Flask 3.1.x, Flask-SocketIO + gevent, paho-mqtt 2.1.0
- **Database**: SQLite with WAL mode
- **Frontend**: Alpine.js 3.x, htmx 2.x, Tailwind CSS v4, Vis.js, Chart.js
- **Real-time**: Socket.IO with server-side 100ms batching
- **Scheduling**: APScheduler with GeventScheduler
- **Plugins**: pluggy + subprocess isolation
- **Observability**: structlog + prometheus_client

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/ -q`)
4. Commit your changes
5. Push and open a Pull Request

## License

MIT License — see [LICENSE.md](LICENSE.md) for details.

## Links

- [GitHub Repository](https://github.com/terdia/mqttui)
- [Docker Hub](https://hub.docker.com/r/terdia07/mqttui)
- [Changelog](CHANGELOG.md)
