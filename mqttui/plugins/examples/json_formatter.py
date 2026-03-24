#!/usr/bin/env python3
"""JSON formatter example plugin for mqttui.

Reads a JSON event from stdin, pretty-prints JSON payloads,
and writes the result to stdout following the plugin protocol.

Protocol:
    stdin:  {"event": "on_message", "data": {"topic": "...", "payload": "..."}}
    stdout: {"actions": [{"type": "transform", "result": "..."}]}
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

        payload = data.get("payload", "")
        try:
            parsed = json.loads(payload)
            pretty = json.dumps(parsed, indent=2)
            print(json.dumps({"actions": [{"type": "transform", "result": pretty}]}))
        except (json.JSONDecodeError, TypeError):
            print(json.dumps({"actions": []}))

    except Exception:
        print(json.dumps({"actions": []}))


if __name__ == "__main__":
    main()
