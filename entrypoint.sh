#!/bin/sh

# Default to port 5000 if PORT is not set
PORT="${PORT:-5000}"

# Default to log level info if LOG_LEVEL is not set
LOG_LEVEL="${LOG_LEVEL:-info}"

# Validate and normalize log level
case "${LOG_LEVEL,,}" in 
  debug|info|warning|error|critical) 
    LOG_LEVEL="${LOG_LEVEL,,}"
    ;;
  *)
    echo "Invalid LOG_LEVEL: $LOG_LEVEL - using default: info"
    LOG_LEVEL="info"
    ;;
esac

exec gunicorn --log-level "$LOG_LEVEL" --worker-class eventlet -w 1 -b "0.0.0.0:$PORT" app:app
