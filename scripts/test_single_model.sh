#!/bin/bash

# Quick test script for a single model
# Usage: ./scripts/test_single_model.sh [model_name]
# Example: ./scripts/test_single_model.sh resnet18

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
NODE1_URL="http://localhost:8001"
NODE2_URL="http://localhost:8002"
MODEL_NAME=${1:-resnet18}
ROUND_ID="R-TEST-$(date +%s)"

NUM_ROUNDS=2
NUM_EPOCHS=2
MIN_CLIENTS=2
MIN_FIT_CLIENTS=2
MIN_AVAILABLE_CLIENTS=2
LEARNING_RATE=0.001

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Quick Test: ${MODEL_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get dataset IDs - improved parsing
DATASET1_RESPONSE=$(curl -s "${NODE1_URL}/api/data/list")
DATASET1_ID=$(echo "$DATASET1_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data[0]['dataset_id'] if data else '')" 2>/dev/null || echo "")

DATASET2_RESPONSE=$(curl -s "${NODE2_URL}/api/data/list")
DATASET2_ID=$(echo "$DATASET2_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data[0]['dataset_id'] if data else '')" 2>/dev/null || echo "")

if [ -z "$DATASET1_ID" ] || [ -z "$DATASET2_ID" ]; then
    echo -e "${RED}Error: Could not find datasets${NC}"
    echo "Dataset 1: ${DATASET1_ID}"
    echo "Dataset 2: ${DATASET2_ID}"
    exit 1
fi

echo "Dataset 1: ${DATASET1_ID}"
echo "Dataset 2: ${DATASET2_ID}"
echo ""

# Start Flower server
echo -e "${BLUE}Starting Flower Server...${NC}"
docker compose exec -T central bash -c "
    nohup bash -c '
        export MODEL_NAME=\"${MODEL_NAME}\"
        export NUM_ROUNDS=${NUM_ROUNDS}
        export MIN_CLIENTS=${MIN_CLIENTS}
        export MIN_FIT_CLIENTS=${MIN_FIT_CLIENTS}
        export MIN_AVAILABLE_CLIENTS=${MIN_AVAILABLE_CLIENTS}
        export NUM_EPOCHS=${NUM_EPOCHS}
        export LEARNING_RATE=${LEARNING_RATE}
        export OPTIMIZER=\"adam\"
        export FLOWER_SERVER_ADDRESS=\"0.0.0.0:8080\"
        python -m app.flower_server > /tmp/flower_${MODEL_NAME}.log 2>&1
    ' > /dev/null 2>&1 &
    echo \$! > /tmp/flower_server.pid
" &

echo "Waiting 15 seconds for server..."
sleep 15
echo ""

# Start training on both nodes
echo -e "${BLUE}Starting training on Node1...${NC}"
JOB1_RESPONSE=$(curl -s -X POST "${NODE1_URL}/api/federated/train/${ROUND_ID}?dataset_id=${DATASET1_ID}&model_name=${MODEL_NAME}")
JOB1_ID=$(echo "$JOB1_RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo "Job ID: ${JOB1_ID}"

echo -e "${BLUE}Starting training on Node2...${NC}"
JOB2_RESPONSE=$(curl -s -X POST "${NODE2_URL}/api/federated/train/${ROUND_ID}?dataset_id=${DATASET2_ID}&model_name=${MODEL_NAME}")
JOB2_ID=$(echo "$JOB2_RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo "Job ID: ${JOB2_ID}"
echo ""

# Monitor progress
echo -e "${BLUE}Monitoring progress...${NC}"
MAX_WAIT=350
ELAPSED=0
CHECK_INTERVAL=10

while [ $ELAPSED -lt $MAX_WAIT ]; do
    JOB1_STATUS=$(curl -s "${NODE1_URL}/api/train/status/${JOB1_ID}" 2>/dev/null | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4 | tr -d '\n\r ')
    JOB2_STATUS=$(curl -s "${NODE2_URL}/api/train/status/${JOB2_ID}" 2>/dev/null | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4 | tr -d '\n\r ')
    
    JOB1_STATUS=${JOB1_STATUS:-unknown}
    JOB2_STATUS=${JOB2_STATUS:-unknown}
    
    # Only print if status changed or every 30 seconds
    if [ $((ELAPSED % 30)) -eq 0 ] || [ "$ELAPSED" -eq 0 ]; then
        echo -e "  Node1: ${JOB1_STATUS} | Node2: ${JOB2_STATUS} | Elapsed: ${ELAPSED}s"
    fi
    
    # Check for completion
    if [ "$JOB1_STATUS" = "completed" ] && [ "$JOB2_STATUS" = "completed" ]; then
        echo ""
        echo -e "${GREEN}✓ Both nodes completed!${NC}"
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
    
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

# Cleanup Flower server
echo ""
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

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Test completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Show logs
echo -e "${BLUE}Federated Logs (Node1):${NC}"
curl -s "http://localhost:8001/api/jobs/${JOB1_ID}/logs/static" | python3 -m json.tool | head -30
echo ""
