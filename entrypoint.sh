#!/bin/sh

# Default to port 5000 if PORT is not set
PORT="${PORT:-5000}"
# Default to INFO if LOG_LEVEL is not set
if [ ! "$LOG_LEVEL" = "debug" ] || [ ! "$LOG_LEVEL" = "DEBUG" ] || [ ! "$LOG_LEVEL" = "info" ] || [ ! "$LOG_LEVEL" = "INFO" ] || [ ! "$LOG_LEVEL" = "warning" ] || [ ! "$LOG_LEVEL" = "WARNING" ] || [ ! "$LOG_LEVEL" = "error" ] || [ ! "$LOG_LEVEL" = "ERROR" ] || [ ! "$LOG_LEVEL" = "critical" ] || [ ! "$LOG_LEVEL" = "CRITICAL" ]; then
    LOG_LEVEL="${LOG_LEVEL:info}"
fi

if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "1" ] || [ "$DEBUG" = "true" ]; then
    echo "Running in DEBUG mode"
    exec python -c "from app import app, socketio; socketio.run(app, host='0.0.0.0', port=$PORT, debug=True)"
else
    echo "Running in PRODUCTION mode"
    exec gunicorn --log-level "$LOG_LEVEL" --worker-class eventlet -w 1 -b "0.0.0.0:$PORT" app:app
fi
