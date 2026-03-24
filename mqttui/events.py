from blinker import Namespace

mqttui_signals = Namespace()

# Fired when an MQTT message is received from the broker
# sender: mqtt_client module, kwargs: topic, payload, timestamp, qos, retain
mqtt_message_received = mqttui_signals.signal('mqtt-message-received')

# Fired when an automation rule fires (Phase 3 will use this)
# sender: rules engine, kwargs: rule_id, rule_name, topic, payload
rule_fired = mqttui_signals.signal('rule-fired')

# Fired when an alert is triggered (Phase 4 will use this)
# sender: alerting module, kwargs: alert_id, rule_id, message
alert_triggered = mqttui_signals.signal('alert-triggered')
