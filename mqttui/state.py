"""
Module-level shared state for in-memory MQTT data.
Imported by routes and MQTT handlers.
"""

messages = []
topics = set()
connection_count = 0
active_websockets = 0
error_log = []
