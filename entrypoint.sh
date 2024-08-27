#!/bin/sh

# Default to port 5000 if PORT is not set
PORT="${PORT:-5000}"

if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "1" ] || [ "$DEBUG" = "true" ]; then
    echo "Running in DEBUG mode"
    exec python -c "from app import app, socketio; socketio.run(app, host='0.0.0.0', port=$PORT, debug=True)"
else
    echo "Running in PRODUCTION mode"
    exec gunicorn --worker-class eventlet -w 1 -b "0.0.0.0:$PORT" app:app
fi
