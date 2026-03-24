#!/usr/bin/env python3
"""Topic logger example plugin for mqttui.

Reads a JSON event from stdin, logs the topic and payload to stderr,
and writes a log action to stdout following the plugin protocol.

Protocol:
    stdin:  {"event": "on_message", "data": {"topic": "...", "payload": "..."}}
    stdout: {"actions": [{"type": "log", "message": "Topic: ..., Payload: ..."}]}
"""
import json
import sys


def main():
    try:
        line = sys.stdin.readline()
        if not line:
            print(json.dumps({"actions": []}))
            return

        envelope = json.loads(line)
        event = envelope.get("event", "")
        data = envelope.get("data", {})

        if event != "on_message":
            print(json.dumps({"actions": []}))
            return

        topic = data.get("topic", "")
        payload = data.get("payload", "")

        # Log to stderr (stdout is reserved for protocol)
        print(f"[topic_logger] Topic: {topic}, Payload: {payload}", file=sys.stderr)

        # Return log action via protocol
        message = f"Topic: {topic}, Payload: {payload}"
        print(json.dumps({"actions": [{"type": "log", "message": message}]}))

    except Exception:
        print(json.dumps({"actions": []}))


if __name__ == "__main__":
    main()
