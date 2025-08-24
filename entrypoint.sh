#!/bin/sh

# Default to port 5000 if PORT is not set
PORT="${PORT:-5000}"

# Set default LOG_LEVEL if not provided
LOG_LEVEL="${LOG_LEVEL:-info}"

# Convert to lowercase for comparison (sh compatible)
LOG_LEVEL_LOWER=$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')

# Validate and normalize log level for gunicorn
case "$LOG_LEVEL_LOWER" in
  debug|info|warning|warn|error|critical)
    # Convert WARN to WARNING for gunicorn compatibility
    if [ "$LOG_LEVEL_LOWER" = "warn" ]; then
      LOG_LEVEL="warning"
    else
      LOG_LEVEL="$LOG_LEVEL_LOWER"
    fi
    ;;
  *)
    echo "Invalid LOG_LEVEL: $LOG_LEVEL. Using default: info"
    LOG_LEVEL="info"
    ;;
esac

if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "1" ] || [ "$DEBUG" = "true" ]; then
    echo "Running in DEBUG mode with log level: $LOG_LEVEL"
    exec python -c "from app import app, socketio; socketio.run(app, host='0.0.0.0', port=$PORT, debug=True)"
else
    echo "Running in PRODUCTION mode with log level: $LOG_LEVEL"
    exec gunicorn --log-level "$LOG_LEVEL" --worker-class eventlet -w 1 -b "0.0.0.0:$PORT" app:app
fi
