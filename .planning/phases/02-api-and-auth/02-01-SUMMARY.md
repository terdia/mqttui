---
phase: 02-api-and-auth
plan: 01
subsystem: auth
tags: [flask-login, flask-sqlalchemy, authentication, login, bcrypt]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Flask app factory, extensions pattern, test infrastructure
provides:
  - User model with password hashing and API token field
  - Flask-Login session-based authentication
  - Auth blueprint with login/logout routes
  - Admin user auto-seeding from env vars
  - SECRET_KEY production guard
  - login_required protection on index and publish routes
affects: [02-api-and-auth, 03-automation-engine, 04-websocket-and-realtime]

# Tech tracking
tech-stack:
  added: [Flask-SQLAlchemy==3.1.1, Flask-Login==0.6.3]
  patterns: [blueprint-based auth, user_loader callback, seed_admin_user pattern, pbkdf2:sha256 hashing]

key-files:
  created: [mqttui/models.py, mqttui/auth.py, templates/login.html]
  modified: [mqttui/extensions.py, mqttui/app.py, mqttui/routes/main.py, tests/conftest.py, tests/test_routes.py, requirements.txt]

key-decisions:
  - "Used pbkdf2:sha256 hashing instead of default scrypt for Python 3.9 compatibility"
  - "Used sa as SQLAlchemy instance name to avoid collision with existing db (MessageDatabase)"
  - "Separate SQLite database (mqttui_users.db) for user data, distinct from message database"

patterns-established:
  - "Auth blueprint pattern: mqttui/auth.py exports auth_bp and seed_admin_user"
  - "User model pattern: UserMixin + sa.Model with is_active_user column"
  - "Protected route pattern: @login_required decorator on routes needing auth"

requirements-completed: [AUTH-01, AUTH-02, AUTH-04]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 02 Plan 01: User Authentication Summary

**Flask-Login session auth with User model, admin seeding, login/logout routes, and SECRET_KEY production guard**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T08:50:15Z
- **Completed:** 2026-03-24T08:53:04Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- User model with password hashing (pbkdf2:sha256), API token generation, and Flask-Login integration
- Auth blueprint with login/logout routes, admin user auto-seeding from MQTTUI_ADMIN_USER/MQTTUI_ADMIN_PASSWORD env vars
- SECRET_KEY production guard that refuses to start with insecure keys
- Protected routes redirect unauthenticated users to /login
- Dark-themed login page matching existing UI

## Task Commits

Each task was committed atomically:

1. **Task 1: Create User model and Flask-SQLAlchemy setup** - `9f730e4` (feat)
2. **Task 2: Create auth blueprint, wire into app factory, add SECRET_KEY guard** - `9031804` (feat)

## Files Created/Modified
- `mqttui/models.py` - User model with password hashing, API token, Flask-Login UserMixin
- `mqttui/auth.py` - Auth blueprint with login/logout routes, user_loader, admin seeding
- `mqttui/extensions.py` - Added SQLAlchemy (sa) and LoginManager instances
- `mqttui/app.py` - Wired sa.init_app, login_manager.init_app, SECRET_KEY guard, auth blueprint
- `mqttui/routes/main.py` - Added @login_required to index and publish_message
- `templates/login.html` - Dark-themed login page with Tailwind CSS
- `tests/conftest.py` - Added SQLALCHEMY_DATABASE_URI for test isolation
- `tests/test_routes.py` - Updated index test for auth redirect, added authenticated test
- `requirements.txt` - Added Flask-SQLAlchemy and Flask-Login

## Decisions Made
- Used `pbkdf2:sha256` for password hashing instead of Werkzeug's default `scrypt` which requires Python 3.10+
- Named SQLAlchemy instance `sa` to avoid collision with existing `db` variable (MessageDatabase)
- Separate SQLite database file (mqttui_users.db) for user data, keeping message DB independent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed password hashing for Python 3.9 compatibility**
- **Found during:** Task 2 (verification)
- **Issue:** Werkzeug's default `scrypt` hashing requires `hashlib.scrypt` which is unavailable in Python 3.9
- **Fix:** Specified `method='pbkdf2:sha256'` in `generate_password_hash()` call
- **Files modified:** mqttui/models.py
- **Verification:** All auth tests pass, password hashing and verification works
- **Committed in:** 9031804 (Task 2 commit)

**2. [Rule 1 - Bug] Updated existing test for auth redirect behavior**
- **Found during:** Task 2 (pytest run)
- **Issue:** `test_index_returns_200` expected 200 but now gets 302 due to @login_required
- **Fix:** Replaced with `test_index_redirects_unauthenticated` and added `test_index_returns_200_authenticated`
- **Files modified:** tests/test_routes.py
- **Verification:** All 16 tests pass
- **Committed in:** 9031804 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required. Admin user is auto-seeded with defaults (admin/admin).

## Next Phase Readiness
- Authentication foundation complete for API token auth (Plan 02-02)
- User model has api_token field ready for token-based API authentication
- login_required pattern established for protecting additional routes

---
*Phase: 02-api-and-auth*
*Completed: 2026-03-24*
