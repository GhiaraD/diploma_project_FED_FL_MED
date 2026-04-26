#!/bin/bash

# Quick single FL test to verify improvements

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
NODE1_URL="http://localhost:8001"
NODE2_URL="http://localhost:8002"
MODEL_NAME="resnet18"
ROUND_ID="R-TEST-$(date +%s)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Quick FL Test - Verify Improvements${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get datasets
echo -e "${BLUE}Getting active datasets...${NC}"
DATASET1_ID=$(curl -s "${NODE1_URL}/api/data/list" | python3 -c "import sys, json; data = json.load(sys.stdin); active = [d for d in data if d['is_active']]; print(active[0]['dataset_id'] if active else '')")
DATASET2_ID=$(curl -s "${NODE2_URL}/api/data/list" | python3 -c "import sys, json; data = json.load(sys.stdin); active = [d for d in data if d['is_active']]; print(active[0]['dataset_id'] if active else '')")

echo -e "${GREEN}✓ Node1 dataset: ${DATASET1_ID}${NC}"
echo -e "${GREEN}✓ Node2 dataset: ${DATASET2_ID}${NC}"
echo ""

# Start Flower server
echo -e "${BLUE}Starting Flower server...${NC}"
docker compose exec -T central bash -c "
cd /app &&
MODEL_NAME='${MODEL_NAME}' \
NUM_ROUNDS=1 \
MIN_CLIENTS=2 \
MIN_FIT_CLIENTS=2 \
MIN_AVAILABLE_CLIENTS=2 \
NUM_EPOCHS=2 \
LEARNING_RATE=0.001 \
OPTIMIZER='adam' \
FLOWER_SERVER_ADDRESS='0.0.0.0:8080' \
python -m app.flower_server > /tmp/flower_${MODEL_NAME}.log 2>&1 &
echo \$! > /tmp/flower_server.pid
sleep 2
" &

sleep 15
echo -e "${GREEN}✓ Flower server started${NC}"
echo ""

# Start training
echo -e "${BLUE}Starting training on Node1...${NC}"
JOB1_RESPONSE=$(curl -s -X POST "${NODE1_URL}/api/federated/train/${ROUND_ID}?dataset_id=${DATASET1_ID}&model_name=${MODEL_NAME}")
JOB1_ID=$(echo $JOB1_RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo -e "${GREEN}✓ Job ID: ${JOB1_ID}${NC}"
echo ""

echo -e "${BLUE}Starting training on Node2...${NC}"
JOB2_RESPONSE=$(curl -s -X POST "${NODE2_URL}/api/federated/train/${ROUND_ID}?dataset_id=${DATASET2_ID}&model_name=${MODEL_NAME}")
JOB2_ID=$(echo $JOB2_RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo -e "${GREEN}✓ Job ID: ${JOB2_ID}${NC}"
echo ""

# Monitor
echo -e "${BLUE}Monitoring training (max 5 minutes)...${NC}"
MAX_WAIT=300
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    JOB1_STATUS=$(curl -s "${NODE1_URL}/api/train/status/${JOB1_ID}" 2>/dev/null | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4 | tr -d '\n\r ')
    JOB2_STATUS=$(curl -s "${NODE2_URL}/api/train/status/${JOB2_ID}" 2>/dev/null | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4 | tr -d '\n\r ')
    
    JOB1_STATUS=${JOB1_STATUS:-unknown}
    JOB2_STATUS=${JOB2_STATUS:-unknown}
    
    # Only print every 30 seconds to reduce spam
    if [ $((ELAPSED % 30)) -eq 0 ] || [ "$ELAPSED" -eq 0 ]; then
        echo "  [${ELAPSED}s] Node1: ${JOB1_STATUS} | Node2: ${JOB2_STATUS}"
    fi
    
    # Check for completion
    if [ "$JOB1_STATUS" = "completed" ] && [ "$JOB2_STATUS" = "completed" ]; then
        echo ""
        echo -e "${GREEN}✓ Training completed!${NC}"
        break
    fi
    
    # Check for failure
    if [ "$JOB1_STATUS" = "failed" ] || [ "$JOB2_STATUS" = "failed" ]; then
        echo ""
        echo -e "${RED}✗ Training failed${NC}"
        exit 1
    fi
    
    # Check for timeout before sleeping
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo ""
        echo -e "${RED}✗ Timeout after ${MAX_WAIT} seconds${NC}"
        exit 1
    fi
    
    sleep 10
    ELAPSED=$((ELAPSED + 10))
done


echo ""

# Verify results
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verifying Results${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}Node1 Job Result:${NC}"
curl -s "${NODE1_URL}/api/train/status/${JOB1_ID}" | python3 -m json.tool | grep -A 20 '"result"'
echo ""

echo -e "${YELLOW}Checking for required fields:${NC}"
JOB1_RESULT=$(curl -s "${NODE1_URL}/api/train/status/${JOB1_ID}")

# Check dataset_id
if echo "$JOB1_RESULT" | grep -q '"dataset_id"'; then
    DATASET_ID=$(echo "$JOB1_RESULT" | python3 -c "import sys, json; r = json.load(sys.stdin).get('result', {}); print(r.get('dataset_id', 'N/A'))")
    echo -e "  ${GREEN}✓ dataset_id: ${DATASET_ID}${NC}"
else
    echo -e "  ${RED}✗ dataset_id: MISSING${NC}"
fi

# Check dataset_name
if echo "$JOB1_RESULT" | grep -q '"dataset_name"'; then
    DATASET_NAME=$(echo "$JOB1_RESULT" | python3 -c "import sys, json; r = json.load(sys.stdin).get('result', {}); print(r.get('dataset_name', 'N/A'))")
    echo -e "  ${GREEN}✓ dataset_name: ${DATASET_NAME}${NC}"
else
    echo -e "  ${RED}✗ dataset_name: MISSING${NC}"
fi

# Check metrics
if echo "$JOB1_RESULT" | grep -q '"metrics"'; then
    METRICS=$(echo "$JOB1_RESULT" | python3 -c "import sys, json; r = json.load(sys.stdin).get('result', {}); m = r.get('metrics'); print('Present' if m else 'N/A')")
    echo -e "  ${GREEN}✓ metrics: ${METRICS}${NC}"
    
    # Show metrics details
    echo "$JOB1_RESULT" | python3 -c "
import sys, json
r = json.load(sys.stdin).get('result', {})
m = r.get('metrics', {})
if m:
    print(f\"    - accuracy: {m.get('accuracy', 'N/A')}\")
    print(f\"    - train_loss: {m.get('train_loss', 'N/A')}\")
    print(f\"    - val_loss: {m.get('val_loss', 'N/A')}\")
"
else
    echo -e "  ${RED}✗ metrics: MISSING${NC}"
fi

echo ""

# Check federated history
echo -e "${YELLOW}Federated History:${NC}"
curl -s "${NODE1_URL}/api/federated/history" | python3 -c "
import sys, json
data = json.load(sys.stdin)
rounds = data.get('rounds', [])
test_round = next((r for r in rounds if r['round_id'] == '${ROUND_ID}'), None)
if test_round:
    print(f\"  ✓ Round found: {test_round['round_id']}\")
    print(f\"    - dataset_id: {test_round.get('dataset_id', 'N/A')}\")
    print(f\"    - dataset_name: {test_round.get('dataset_name', 'N/A')}\")
    metrics = test_round.get('metrics', {})
    if metrics:
        print(f\"    - accuracy: {metrics.get('accuracy', 'N/A')}\")
    else:
        print(f\"    - metrics: N/A\")
else:
    print('  ✗ Round not found in history')
"

echo ""

# Cleanup
echo -e "${BLUE}Stopping Flower server...${NC}"
docker compose exec -T central bash -c "
    if [ -f /tmp/flower_server.pid ]; then
        pid=\$(cat /tmp/flower_server.pid)
        if [ -n \"\$pid\" ]; then
            kill -9 \$pid 2>/dev/null || true
            rm /tmp/flower_server.pid
        fi
    fi
" 2>/dev/null || true

echo -e "${GREEN}✓ Test complete!${NC}"
echo ""
