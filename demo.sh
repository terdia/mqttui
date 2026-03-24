#!/bin/bash
# =============================================================================
# MQTTUI v2.0 Demo Script
# Populates realistic MQTT data to test all features end-to-end
# Usage: ./demo.sh
# Requires: docker compose running (mosquitto + mqttui containers)
# =============================================================================

set -e

BROKER_CONTAINER="mosquitto"
API_URL="http://localhost:8088/api/v1"
PUB="docker exec $BROKER_CONTAINER mosquitto_pub"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE} MQTTUI v2.0 Demo Data Generator${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check containers are running
if ! docker ps --format '{{.Names}}' | grep -q "$BROKER_CONTAINER"; then
    echo "Error: $BROKER_CONTAINER container not running. Run: docker compose up -d"
    exit 1
fi

# ---------------------------------------------------------------------------
# 1. Login and get session cookie
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[1/7] Authenticating...${NC}"
COOKIE_JAR="/tmp/mqttui-demo-cookies.txt"
LOGIN_RESP=$(curl -s -c "$COOKIE_JAR" -X POST "http://localhost:8088/login" \
    -d "username=admin&password=admin" \
    -L -o /dev/null -w "%{http_code}")

if [ "$LOGIN_RESP" != "200" ]; then
    echo "  Login failed (HTTP $LOGIN_RESP). Check MQTTUI_ADMIN_USER/PASSWORD."
    exit 1
fi
echo -e "  ${GREEN}✓ Logged in as admin${NC}"

# ---------------------------------------------------------------------------
# 2. Publish varied MQTT messages (tests Dashboard, Message Flow, Analytics)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[2/7] Publishing 200 MQTT messages across 5 device types...${NC}"

# Temperature sensors (numeric, good for histograms)
for i in $(seq 1 50); do
    temp=$(echo "scale=1; 18 + ($RANDOM % 200) / 10" | bc)
    $PUB -t "sensors/living-room/temperature" -m "{\"value\": $temp, \"unit\": \"C\", \"device\": \"DHT22\"}"
    $PUB -t "sensors/bedroom/temperature" -m "{\"value\": $temp, \"unit\": \"C\", \"device\": \"DHT22\"}"
done
echo -e "  ${GREEN}✓ 100 temperature readings (18-38°C range)${NC}"

# Humidity sensors
for i in $(seq 1 30); do
    humidity=$((40 + RANDOM % 40))
    $PUB -t "sensors/living-room/humidity" -m "{\"value\": $humidity, \"unit\": \"%\", \"device\": \"DHT22\"}"
done
echo -e "  ${GREEN}✓ 30 humidity readings${NC}"

# Motion sensors (binary events)
for i in $(seq 1 20); do
    room=$(echo "hallway kitchen garage front-door" | tr ' ' '\n' | shuf -n1)
    $PUB -t "sensors/$room/motion" -m "{\"detected\": true, \"confidence\": $((70 + RANDOM % 30))}"
done
echo -e "  ${GREEN}✓ 20 motion events${NC}"

# Battery levels (good for threshold alerting)
for i in $(seq 1 20); do
    device=$(echo "thermostat doorbell smoke-detector leak-sensor" | tr ' ' '\n' | shuf -n1)
    battery=$((5 + RANDOM % 95))
    $PUB -t "devices/$device/battery" -m "{\"level\": $battery, \"charging\": false}"
done
echo -e "  ${GREEN}✓ 20 battery readings${NC}"

# System status messages (retained)
$PUB -t "system/mqttui/status" -m '{"status": "online", "version": "2.0.0"}' -r
$PUB -t "system/broker/status" -m '{"status": "online", "clients": 5}' -r
echo -e "  ${GREEN}✓ 2 retained status messages${NC}"

# Home automation commands
for i in $(seq 1 28); do
    device=$(echo "light-1 light-2 fan ac heater" | tr ' ' '\n' | shuf -n1)
    state=$(echo "on off" | tr ' ' '\n' | shuf -n1)
    $PUB -t "home/$device/command" -m "{\"state\": \"$state\", \"source\": \"automation\"}"
done
echo -e "  ${GREEN}✓ 28 home automation commands${NC}"

echo -e "  ${GREEN}Total: 200 messages across 15+ topics${NC}"

# ---------------------------------------------------------------------------
# 3. Create automation rules (tests Rules tab)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[3/7] Creating automation rules...${NC}"

# Rule 1: High temperature alert (publish action)
curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "High Temperature Alert",
        "description": "Publish alert when any temperature exceeds 35°C",
        "trigger_topic": "sensors/+/temperature",
        "condition": {"path": "value", "op": "gt", "value": 35},
        "action": {"type": "publish", "topic": "alerts/high-temp", "payload": "{\"alert\": \"Temperature exceeded 35°C\"}"},
        "rate_limit_per_min": 5
    }' > /dev/null
echo -e "  ${GREEN}✓ High Temperature Alert (publish to alerts/high-temp when > 35°C)${NC}"

# Rule 2: Low battery warning (log action)
curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Low Battery Warning",
        "description": "Log when any device battery drops below 20%",
        "trigger_topic": "devices/+/battery",
        "condition": {"path": "level", "op": "lt", "value": 20},
        "action": {"type": "log", "severity": "warning", "message": "Low battery detected"},
        "rate_limit_per_min": 10
    }' > /dev/null
echo -e "  ${GREEN}✓ Low Battery Warning (log when battery < 20%)${NC}"

# Rule 3: Motion logger (log action, no condition)
curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Motion Event Logger",
        "description": "Log all motion detection events",
        "trigger_topic": "sensors/+/motion",
        "condition": {},
        "action": {"type": "log", "severity": "info", "message": "Motion detected"},
        "rate_limit_per_min": 30
    }' > /dev/null
echo -e "  ${GREEN}✓ Motion Event Logger (log all motion events)${NC}"

# Rule 4: Wildcard monitor (disabled by default)
RULE4_RESP=$(curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "All Messages Monitor",
        "description": "Monitor everything (disabled - enable for debugging)",
        "trigger_topic": "#",
        "condition": {},
        "action": {"type": "log", "severity": "info", "message": "Message received"},
        "rate_limit_per_min": 60
    }')
RULE4_ID=$(echo "$RULE4_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('id',''))" 2>/dev/null)
if [ -n "$RULE4_ID" ]; then
    curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/$RULE4_ID/disable" > /dev/null
fi
echo -e "  ${GREEN}✓ All Messages Monitor (disabled — for debugging)${NC}"

# ---------------------------------------------------------------------------
# 4. Trigger rules with matching messages (tests Alerts tab)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[4/7] Triggering rules with matching messages...${NC}"

# Trigger high temp alert
for i in $(seq 1 5); do
    temp=$(echo "scale=1; 36 + ($RANDOM % 50) / 10" | bc)
    $PUB -t "sensors/living-room/temperature" -m "{\"value\": $temp, \"unit\": \"C\", \"device\": \"DHT22\"}"
    sleep 0.3
done
echo -e "  ${GREEN}✓ 5 high-temp messages (should trigger alerts)${NC}"

# Trigger low battery
for i in $(seq 1 3); do
    device=$(echo "thermostat doorbell smoke-detector" | tr ' ' '\n' | shuf -n1)
    battery=$((3 + RANDOM % 15))
    $PUB -t "devices/$device/battery" -m "{\"level\": $battery, \"charging\": false}"
    sleep 0.3
done
echo -e "  ${GREEN}✓ 3 low-battery messages (should trigger warnings)${NC}"

# Trigger motion
for i in $(seq 1 5); do
    room=$(echo "hallway kitchen garage" | tr ' ' '\n' | shuf -n1)
    $PUB -t "sensors/$room/motion" -m "{\"detected\": true, \"confidence\": $((80 + RANDOM % 20))}"
    sleep 0.2
done
echo -e "  ${GREEN}✓ 5 motion events (should be logged)${NC}"

# Wait for rules to process
sleep 3

# ---------------------------------------------------------------------------
# 5. Create filter presets (tests Advanced Search)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[5/7] Creating filter presets...${NC}"

curl -s -b "$COOKIE_JAR" -X POST "$API_URL/filter-presets" \
    -H "Content-Type: application/json" \
    -d '{"name": "Temperature Only", "description": "All temperature sensors", "filters": {"regex_topic": "sensors/.*/temperature"}}' > /dev/null
echo -e "  ${GREEN}✓ 'Temperature Only' preset${NC}"

curl -s -b "$COOKIE_JAR" -X POST "$API_URL/filter-presets" \
    -H "Content-Type: application/json" \
    -d '{"name": "Alerts & Warnings", "description": "Alert topics only", "filters": {"regex_topic": "alerts/.*"}}' > /dev/null
echo -e "  ${GREEN}✓ 'Alerts & Warnings' preset${NC}"

curl -s -b "$COOKIE_JAR" -X POST "$API_URL/filter-presets" \
    -H "Content-Type: application/json" \
    -d '{"name": "Low Battery Devices", "description": "Battery below 30%", "filters": {"regex_topic": "devices/.*/battery", "json_path": "level", "json_value": "30"}}' > /dev/null
echo -e "  ${GREEN}✓ 'Low Battery Devices' preset${NC}"

# ---------------------------------------------------------------------------
# 6. Bookmark favorite topics (tests Topic Favorites)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[6/7] Bookmarking favorite topics...${NC}"

for topic in "sensors/living-room/temperature" "sensors/bedroom/temperature" "devices/thermostat/battery"; do
    curl -s -b "$COOKIE_JAR" -X POST "$API_URL/topics/$(echo $topic | sed 's/\//%2F/g')/bookmark" > /dev/null 2>&1
    echo -e "  ${GREEN}✓ Bookmarked: $topic${NC}"
done

# ---------------------------------------------------------------------------
# 7. Verify data via API
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[7/7] Verifying data via API...${NC}"

MSG_COUNT=$(curl -s -b "$COOKIE_JAR" "$API_URL/messages?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',d).get('total',0))" 2>/dev/null)
echo -e "  Messages stored: ${GREEN}$MSG_COUNT${NC}"

RULE_COUNT=$(curl -s -b "$COOKIE_JAR" "$API_URL/rules/" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',d).get('rules',[])))" 2>/dev/null)
echo -e "  Rules created: ${GREEN}$RULE_COUNT${NC}"

ALERT_COUNT=$(curl -s -b "$COOKIE_JAR" "$API_URL/alerts/" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',d).get('total',0))" 2>/dev/null)
echo -e "  Alerts fired: ${GREEN}$ALERT_COUNT${NC}"

ANALYTICS=$(curl -s -b "$COOKIE_JAR" "$API_URL/analytics/topics?limit=5" | python3 -c "
import sys,json
d=json.load(sys.stdin)
topics = d.get('data',d).get('topics',[])
for t in topics[:5]:
    print(f\"    {t['topic']}: {t.get('rate_per_min',0):.0f}/min, {t.get('message_count',0)} msgs\")
" 2>/dev/null)
echo -e "  Analytics (top 5 topics):"
echo -e "${GREEN}$ANALYTICS${NC}"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE} Demo Data Ready!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Open ${GREEN}http://localhost:8088${NC} and check:"
echo ""
echo -e "  ${YELLOW}Dashboard${NC}"
echo "    - Message list with 200+ messages"
echo "    - Topic graph with 15+ nodes"
echo "    - Message rate chart updating"
echo "    - Retained messages marked with 'R' badge"
echo "    - Bookmarked topics starred in dropdown"
echo ""
echo -e "  ${YELLOW}Rules${NC}"
echo "    - 4 rules (3 active, 1 disabled)"
echo "    - Click Edit to see pre-filled form"
echo "    - Click Test for dry-run against sample payload"
echo "    - High Temp rule should show fire count > 0"
echo ""
echo -e "  ${YELLOW}Alerts${NC}"
echo "    - Alert history from rule firings"
echo "    - Filter by rule or severity"
echo ""
echo -e "  ${YELLOW}Analytics${NC}"
echo "    - Per-topic message rates"
echo "    - Payload histograms (temperature values)"
echo "    - Top topics by activity"
echo ""
echo -e "  ${YELLOW}Plugins${NC}"
echo "    - JSON Formatter and Topic Logger listed"
echo "    - Enable/disable toggles"
echo ""
echo -e "  ${YELLOW}Other${NC}"
echo "    - Debug bar (blue button, bottom-right)"
echo "    - API docs: http://localhost:8088/api/v1/docs"
echo "    - Prometheus: http://localhost:8088/metrics"
echo ""

# Cleanup
rm -f "$COOKIE_JAR"
