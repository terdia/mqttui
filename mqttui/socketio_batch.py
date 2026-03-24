import threading
from flask_socketio import SocketIO


class BatchEmitter:
    """Collects MQTT messages and emits them in batches every 100ms.

    This prevents UI flooding at high throughput by buffering messages
    server-side and sending them in consolidated batches.
    """

    def __init__(self, socketio: SocketIO, interval_ms: int = 100):
        self._socketio = socketio
        self._interval = interval_ms / 1000.0
        self._buffer = []
        self._lock = threading.Lock()
        self._timer = None
        self._running = False

    def start(self):
        """Start the periodic flush timer."""
        self._running = True
        self._schedule_flush()

    def stop(self):
        """Stop the periodic flush timer."""
        self._running = False
        if self._timer:
            self._timer.cancel()

    def enqueue(self, message: dict):
        """Add a message to the batch buffer (thread-safe)."""
        with self._lock:
            self._buffer.append(message)

    def _schedule_flush(self):
        """Schedule the next flush cycle."""
        if not self._running:
            return
        self._timer = threading.Timer(self._interval, self._flush)
        self._timer.daemon = True
        self._timer.start()

    def _flush(self):
        """Emit buffered messages as a batch and reschedule."""
        with self._lock:
            batch = self._buffer
            self._buffer = []
        if batch:
            self._socketio.emit('mqtt_messages_batch', batch)
        self._schedule_flush()


_batch_emitter = None


def init_batch_emitter(socketio: SocketIO, interval_ms: int = 100):
    """Initialize and start the global batch emitter.

    Called once in create_app after socketio.init_app().
    """
    global _batch_emitter
    _batch_emitter = BatchEmitter(socketio, interval_ms)
    _batch_emitter.start()
    return _batch_emitter


def get_batch_emitter():
    """Return the global batch emitter instance."""
    return _batch_emitter
