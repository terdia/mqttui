#!/bin/bash
# =============================================================================
# MQTTUI v2.1 Demo Script
# Populates realistic MQTT data across multiple brokers to test all features
# Usage: ./demo.sh
# Requires: docker compose running (mosquitto + mosquitto2 + mqttui containers)
# =============================================================================

set -e

BROKER1="mosquitto"
BROKER2="mosquitto2"
API_URL="http://localhost:8088/api/v1"
PUB1="docker exec $BROKER1 mosquitto_pub"
PUB2="docker exec $BROKER2 mosquitto_pub"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE} MQTTUI v2.1 Demo Data Generator (Multi-Broker)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check containers are running
for c in $BROKER1 $BROKER2 mqttui; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${c}$"; then
        echo "Error: $c container not running. Run: docker compose up -d"
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# 1. Login and get session cookie
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[1/8] Authenticating...${NC}"
COOKIE_JAR="/tmp/mqttui-demo-cookies.txt"
LOGIN_RESP=$(curl -s -c "$COOKIE_JAR" -X POST "http://localhost:8088/login" \
    -d "username=admin&password=admin" \
    -o /dev/null -w "%{http_code}")

if [ "$LOGIN_RESP" != "302" ] && [ "$LOGIN_RESP" != "200" ]; then
    echo "  Login failed (HTTP $LOGIN_RESP). Check MQTTUI_ADMIN_USER/PASSWORD."
    exit 1
fi
echo -e "  ${GREEN}✓ Logged in as admin${NC}"

# ---------------------------------------------------------------------------
# 2. Set up second broker connection
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[2/8] Setting up second broker...${NC}"

# Check if Broker 2 already exists
EXISTING=$(curl -s -b "$COOKIE_JAR" "$API_URL/brokers/" | python3 -c "
import sys,json
d=json.load(sys.stdin)
brokers = (d.get('data') or d).get('brokers',[])
print(len([b for b in brokers if b.get('host') == '$BROKER2']))
" 2>/dev/null)

if [ "$EXISTING" = "0" ]; then
    curl -s -b "$COOKIE_JAR" -X POST "$API_URL/brokers/" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"Warehouse\",
            \"host\": \"$BROKER2\",
            \"port\": 1883,
            \"topics\": \"#\",
            \"is_active\": true
        }" > /dev/null
    echo -e "  ${GREEN}✓ Added 'Warehouse' broker ($BROKER2:1883)${NC}"
    sleep 2  # Wait for connection
else
    echo -e "  ${GREEN}✓ Second broker already exists${NC}"
fi

BROKER_COUNT=$(curl -s -b "$COOKIE_JAR" "$API_URL/brokers/" | python3 -c "
import sys,json; d=json.load(sys.stdin)
brokers = (d.get('data') or d).get('brokers',[])
connected = sum(1 for b in brokers if b.get('connected'))
print(f'{connected}/{len(brokers)} connected')
" 2>/dev/null)
echo -e "  Brokers: ${GREEN}$BROKER_COUNT${NC}"

# ---------------------------------------------------------------------------
# 3. Publish to Broker 1 — Home automation sensors
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[3/8] Publishing to Broker 1 (Default) — Home sensors...${NC}"

# Temperature sensors
for i in $(seq 1 40); do
    temp=$(echo "scale=1; 18 + ($RANDOM % 200) / 10" | bc)
    $PUB1 -t "home/living-room/temperature" -m "{\"value\": $temp, \"unit\": \"C\", \"device\": \"DHT22\"}"
    $PUB1 -t "home/bedroom/temperature" -m "{\"value\": $temp, \"unit\": \"C\", \"device\": \"DHT22\"}"
done
echo -e "  ${GREEN}✓ 80 temperature readings${NC}"

# Humidity
for i in $(seq 1 20); do
    humidity=$((40 + RANDOM % 40))
    $PUB1 -t "home/living-room/humidity" -m "{\"value\": $humidity, \"unit\": \"%\"}"
done
echo -e "  ${GREEN}✓ 20 humidity readings${NC}"

# Motion sensors
for i in $(seq 1 15); do
    room=$(echo "hallway kitchen garage front-door" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    $PUB1 -t "home/$room/motion" -m "{\"detected\": true, \"confidence\": $((70 + RANDOM % 30))}"
done
echo -e "  ${GREEN}✓ 15 motion events${NC}"

# Battery levels
for i in $(seq 1 10); do
    device=$(echo "thermostat doorbell smoke-detector leak-sensor" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    battery=$((5 + RANDOM % 95))
    $PUB1 -t "home/$device/battery" -m "{\"level\": $battery, \"charging\": false}"
done
echo -e "  ${GREEN}✓ 10 battery levels${NC}"

# Retained status
$PUB1 -t "system/home/status" -m '{"status": "online", "version": "2.1.0"}' -r
echo -e "  ${GREEN}✓ 1 retained status message${NC}"

echo -e "  ${GREEN}Broker 1 total: 126 messages${NC}"

# ---------------------------------------------------------------------------
# 4. Publish to Broker 2 — Warehouse / industrial sensors
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[4/8] Publishing to Broker 2 (Warehouse) — Industrial sensors...${NC}"

# Warehouse temperature (cold storage monitoring)
for i in $(seq 1 40); do
    temp=$(echo "scale=1; -5 + ($RANDOM % 150) / 10" | bc)
    zone=$(echo "zone-A zone-B zone-C" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    $PUB2 -t "warehouse/$zone/temperature" -m "{\"value\": $temp, \"unit\": \"C\", \"sensor\": \"PT100\"}"
done
echo -e "  ${GREEN}✓ 40 cold storage temperature readings${NC}"

# Conveyor belt speed
for i in $(seq 1 20); do
    line=$(echo "line-1 line-2 line-3" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    speed=$(echo "scale=1; 1 + ($RANDOM % 50) / 10" | bc)
    $PUB2 -t "warehouse/$line/conveyor/speed" -m "{\"value\": $speed, \"unit\": \"m/s\"}"
done
echo -e "  ${GREEN}✓ 20 conveyor speed readings${NC}"

# Door access events
for i in $(seq 1 15); do
    door=$(echo "main loading-dock office emergency" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    action=$(echo "opened closed" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    $PUB2 -t "warehouse/doors/$door" -m "{\"action\": \"$action\", \"badge_id\": \"EMP-$((100 + RANDOM % 900))\"}"
done
echo -e "  ${GREEN}✓ 15 door access events${NC}"

# Power meters
for i in $(seq 1 10); do
    meter=$(echo "main-panel hvac compressor lighting" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    watts=$((500 + RANDOM % 9500))
    $PUB2 -t "warehouse/power/$meter" -m "{\"watts\": $watts, \"voltage\": 240}"
done
echo -e "  ${GREEN}✓ 10 power meter readings${NC}"

# Retained status
$PUB2 -t "system/warehouse/status" -m '{"status": "online", "zones": 3, "conveyors": 3}' -r
echo -e "  ${GREEN}✓ 1 retained status message${NC}"

echo -e "  ${GREEN}Broker 2 total: 86 messages${NC}"

# ---------------------------------------------------------------------------
# 5. Create automation rules (spanning both brokers)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[5/8] Creating automation rules...${NC}"

# Rule 1: High temperature alert (home)
curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Home High Temp Alert",
        "description": "Alert when home temperature exceeds 35°C",
        "trigger_topic": "home/+/temperature",
        "condition": {"path": "value", "op": "gt", "value": 35},
        "action": {"type": "publish", "topic": "alerts/high-temp", "payload": "{\"alert\": \"Home temperature exceeded 35°C\"}"},
        "rate_limit_per_min": 5
    }' > /dev/null
echo -e "  ${GREEN}✓ Home High Temp Alert${NC}"

# Rule 2: Cold storage warning (warehouse — temp too high for cold storage)
curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Cold Storage Warning",
        "description": "Alert when warehouse temp rises above 5°C",
        "trigger_topic": "warehouse/+/temperature",
        "condition": {"path": "value", "op": "gt", "value": 5},
        "action": {"type": "log", "severity": "critical", "message": "Cold storage temperature exceeded threshold"},
        "rate_limit_per_min": 10
    }' > /dev/null
echo -e "  ${GREEN}✓ Cold Storage Warning (warehouse temp > 5°C)${NC}"

# Rule 3: Low battery warning
curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Low Battery Warning",
        "description": "Log when any device battery drops below 20%",
        "trigger_topic": "home/+/battery",
        "condition": {"path": "level", "op": "lt", "value": 20},
        "action": {"type": "log", "severity": "warning", "message": "Low battery detected"},
        "rate_limit_per_min": 10
    }' > /dev/null
echo -e "  ${GREEN}✓ Low Battery Warning${NC}"

# Rule 4: Emergency door monitor (warehouse)
curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Emergency Door Monitor",
        "description": "Log when emergency door is opened",
        "trigger_topic": "warehouse/doors/emergency",
        "condition": {"path": "action", "op": "eq", "value": "opened"},
        "action": {"type": "log", "severity": "critical", "message": "Emergency door opened!"},
        "rate_limit_per_min": 30
    }' > /dev/null
echo -e "  ${GREEN}✓ Emergency Door Monitor${NC}"

# Rule 5: Motion logger
curl -s -b "$COOKIE_JAR" -X POST "$API_URL/rules/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Motion Event Logger",
        "description": "Log all motion detection events",
        "trigger_topic": "home/+/motion",
        "condition": {},
        "action": {"type": "log", "severity": "info", "message": "Motion detected"},
        "rate_limit_per_min": 30
    }' > /dev/null
echo -e "  ${GREEN}✓ Motion Event Logger${NC}"

# ---------------------------------------------------------------------------
# 6. Trigger rules with matching messages
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[6/8] Triggering rules with matching messages...${NC}"

# Trigger home high temp
for i in $(seq 1 5); do
    temp=$(echo "scale=1; 36 + ($RANDOM % 50) / 10" | bc)
    $PUB1 -t "home/living-room/temperature" -m "{\"value\": $temp, \"unit\": \"C\", \"device\": \"DHT22\"}"
    sleep 0.3
done
echo -e "  ${GREEN}✓ 5 high-temp messages on Broker 1${NC}"

# Trigger cold storage warnings
for i in $(seq 1 5); do
    temp=$(echo "scale=1; 6 + ($RANDOM % 40) / 10" | bc)
    zone=$(echo "zone-A zone-B zone-C" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    $PUB2 -t "warehouse/$zone/temperature" -m "{\"value\": $temp, \"unit\": \"C\", \"sensor\": \"PT100\"}"
    sleep 0.3
done
echo -e "  ${GREEN}✓ 5 cold storage warnings on Broker 2${NC}"

# Trigger low battery
for i in $(seq 1 3); do
    device=$(echo "thermostat doorbell smoke-detector" | tr ' ' '\n' | sort -R 2>/dev/null | head -1 || awk 'BEGIN{srand()}{a[NR]=$0}END{print a[int(rand()*NR)+1]}')
    battery=$((3 + RANDOM % 15))
    $PUB1 -t "home/$device/battery" -m "{\"level\": $battery, \"charging\": false}"
    sleep 0.3
done
echo -e "  ${GREEN}✓ 3 low-battery messages${NC}"

# Trigger emergency door
$PUB2 -t "warehouse/doors/emergency" -m '{"action": "opened", "badge_id": "EMP-999"}'
echo -e "  ${GREEN}✓ 1 emergency door event on Broker 2${NC}"

sleep 3

# ---------------------------------------------------------------------------
# 7. Create filter presets + bookmarks
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[7/8] Creating filter presets and bookmarks...${NC}"

curl -s -b "$COOKIE_JAR" -X POST "$API_URL/filter-presets" \
    -H "Content-Type: application/json" \
    -d '{"name": "Home Sensors", "description": "All home sensor data", "filters": {"regex_topic": "home/.*"}}' > /dev/null
echo -e "  ${GREEN}✓ 'Home Sensors' preset${NC}"

curl -s -b "$COOKIE_JAR" -X POST "$API_URL/filter-presets" \
    -H "Content-Type: application/json" \
    -d '{"name": "Warehouse Only", "description": "All warehouse data", "filters": {"regex_topic": "warehouse/.*"}}' > /dev/null
echo -e "  ${GREEN}✓ 'Warehouse Only' preset${NC}"

curl -s -b "$COOKIE_JAR" -X POST "$API_URL/filter-presets" \
    -H "Content-Type: application/json" \
    -d '{"name": "Alerts", "description": "Alert topics only", "filters": {"regex_topic": "alerts/.*"}}' > /dev/null
echo -e "  ${GREEN}✓ 'Alerts' preset${NC}"

for topic in "home/living-room/temperature" "warehouse/zone-A/temperature" "warehouse/doors/emergency"; do
    curl -s -b "$COOKIE_JAR" -X POST "$API_URL/topics/$(echo $topic | sed 's/\//%2F/g')/bookmark" > /dev/null 2>&1
    echo -e "  ${GREEN}✓ Bookmarked: $topic${NC}"
done

# ---------------------------------------------------------------------------
# 8. Verify data via API
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[8/8] Verifying data via API...${NC}"

MSG_COUNT=$(curl -s -b "$COOKIE_JAR" "$API_URL/messages?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',d).get('total',0))" 2>/dev/null)
echo -e "  Messages stored: ${GREEN}$MSG_COUNT${NC}"

BROKER_STATUS=$(curl -s -b "$COOKIE_JAR" "$API_URL/brokers/" | python3 -c "
import sys,json
d=json.load(sys.stdin)
brokers = (d.get('data') or d).get('brokers',[])
for b in brokers:
    status = '✓ Connected' if b.get('connected') else '✗ Disconnected'
    print(f\"    {b['name']} ({b['host']}:{b['port']}): {status}\")
" 2>/dev/null)
echo -e "  Brokers:"
echo -e "${GREEN}$BROKER_STATUS${NC}"

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
echo -e "${BLUE} Demo Data Ready! (Multi-Broker)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Open ${GREEN}http://localhost:8088${NC} and check:"
echo ""
echo -e "  ${YELLOW}Dashboard${NC}"
echo "    - Messages from BOTH brokers (look for broker name badges)"
echo "    - Topic graph with home/* and warehouse/* nodes"
echo "    - Use Broker dropdown in Advanced Search to filter by broker"
echo "    - Use ★ Favorites Only to see bookmarked topics"
echo ""
echo -e "  ${YELLOW}Brokers${NC}"
echo "    - Default (mosquitto) — home automation sensors"
echo "    - Warehouse (mosquitto2) — industrial sensors"
echo "    - Both should show 'Connected' with green indicator"
echo ""
echo -e "  ${YELLOW}Rules${NC}"
echo "    - 5 rules spanning both brokers"
echo "    - Home High Temp + Cold Storage + Low Battery + Emergency Door + Motion"
echo ""
echo -e "  ${YELLOW}Alerts${NC}"
echo "    - Alerts from rules on both brokers"
echo "    - Filter by rule to see per-broker alerts"
echo ""
echo -e "  ${YELLOW}Analytics${NC}"
echo "    - Topics from both brokers in the same view"
echo "    - Temperature histograms for home AND warehouse"
echo ""

rm -f "$COOKIE_JAR"
