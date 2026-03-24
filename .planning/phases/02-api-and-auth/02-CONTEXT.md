# Phase 2: API and Auth - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Formalize all existing endpoints under a versioned /api/v1/ prefix with consistent JSON responses, add OpenAPI documentation, implement username/password authentication with session management, API token support for programmatic access, rate limiting on the publish endpoint, and SECRET_KEY validation in production mode.

</domain>

<decisions>
## Implementation Decisions

### Authentication Approach
- Flask-Login for session management with cookie-based auth (simpler than JWT for self-hosted tool)
- bcrypt password hashing via werkzeug.security (generate_password_hash/check_password_hash)
- Admin user seeded from environment variables: MQTTUI_ADMIN_USER and MQTTUI_ADMIN_PASSWORD
- Users table in SQLite via Flask-SQLAlchemy (id, username, password_hash, api_token, is_active, created_at)
- Login page at /login with redirect to dashboard after success
- Protected routes require @login_required decorator

### API Token Support
- Random 32-byte hex token generated per user, stored in users table
- Passed via X-API-Key header for programmatic/headless access
- Token authentication checked before session auth (allows both methods)
- Token CRUD via /api/v1/auth/token endpoint (regenerate, revoke)

### API Design
- All endpoints under /api/v1/ prefix (versioned from the start)
- Consistent JSON envelope: {"status": "success"|"error", "data": {...}|null, "error": {"code": "...", "message": "..."}|null}
- OpenAPI documentation via flask-apispec + marshmallow schemas, served at /api/v1/docs
- CORS support via Flask-CORS (already in requirements from Phase 1 research)

### Rate Limiting
- Flask-Limiter with in-memory storage (suitable for single-worker deployment)
- Default: 30 requests/minute on /api/v1/publish, configurable via MQTTUI_RATE_LIMIT env var
- 429 Too Many Requests response with Retry-After header
- Rate limit applies per-IP

### Security
- Application refuses to start if SECRET_KEY equals "dev" or "change-me" when FLASK_ENV=production
- Validation check in create_app() factory before first request

### Claude's Discretion
- Exact marshmallow schema structure for each endpoint
- Login page HTML/CSS styling (should match existing dark theme)
- Error code naming convention
- Whether to add Flask-Migrate for the users table migration or use create_all()

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- mqttui/routes/api.py — existing API blueprint with 8 endpoints (messages, topics, database stats, filter presets)
- mqttui/routes/main.py — main UI routes (index, publish, stats, version)
- mqttui/app.py — create_app() factory with blueprint registration
- mqttui/extensions.py — shared SocketIO instance
- mqttui/database.py — MessageDatabase class with SQLite, WAL mode, thread-local connections

### Established Patterns
- Blueprint-based route organization (main_bp, api_bp, debug_bp)
- App factory pattern with create_app()
- Environment variable configuration via python-dotenv
- SQLite with WAL mode and busy_timeout on all connections
- Dark theme Tailwind CSS in templates/index.html

### Integration Points
- api_bp blueprint in mqttui/routes/api.py — needs /api/v1/ prefix added
- create_app() in mqttui/app.py — needs Flask-Login, Flask-Limiter, Flask-CORS init
- requirements.txt — needs new dependencies
- templates/ — needs login.html template
- .env_example — needs new env vars documented

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard auth and API patterns for self-hosted tool

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
