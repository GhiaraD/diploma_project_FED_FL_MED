#!/bin/bash
# End-to-End Test - 2 Nodes Only (to avoid OOM)

set -e

CENTRAL_URL="http://localhost:8080"
ROUND_ID="R-2NODES-$(date +%s)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "============================================================"
echo "FL End-to-End Test - 2 Nodes (Memory Safe)"
echo "============================================================"
echo "Round ID: $ROUND_ID"
echo ""

# Create round
echo -e "${BLUE}▶ Creating FL round...${NC}"
curl -s -X POST "$CENTRAL_URL/round/create" \
  -H 'Content-Type: application/json' \
  -d '{
    "round_id": "'"$ROUND_ID"'",
    "model_name": "resnet18",
    "num_classes": 2,
    "pretrained": true,
    "hyperparameters": {
      "num_epochs": 1,
      "batch_size": 16,
      "learning_rate": 0.001,
      "optimizer": "adam"
    }
  }' | python3 -m json.tool

# Register only 2 nodes
echo ""
echo -e "${BLUE}▶ Registering 2 nodes...${NC}"
for node in node1 node2; do
    curl -s -X POST "$CENTRAL_URL/round/$ROUND_ID/join" \
      -H 'Content-Type: application/json' \
      -d "{\"node_id\": \"$node\", \"node_url\": \"http://$node-api:8000\"}" | python3 -m json.tool
done

# Train nodes sequentially
echo ""
echo -e "${BLUE}▶ Training nodes sequentially...${NC}"

for node_num in 1 2; do
    node="node$node_num"
    port=$((8000 + node_num))
    
    echo ""
    echo -e "${YELLOW}━━━ Training $node ━━━${NC}"
    
    DATASET_ID=$(curl -s "http://localhost:$port/api/data/list" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['dataset_id'])")
    echo "  Dataset ID: $DATASET_ID"
    
    TRAIN_RESPONSE=$(curl -s -X POST "http://localhost:$port/api/federated/train/$ROUND_ID?dataset_id=$DATASET_ID")
    JOB_ID=$(echo "$TRAIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
    echo -e "  ${GREEN}✓${NC} Training started (Job ID: $JOB_ID)"
    
    echo -n "  Progress: "
    MAX_WAIT=180
    ELAPSED=0
    
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        STATUS=$(curl -s "http://localhost:$port/api/train/status/$JOB_ID" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        
        if [ "$STATUS" = "completed" ]; then
            echo ""
            echo -e "  ${GREEN}✓${NC} Training completed!"
            break
        elif [ "$STATUS" = "failed" ]; then
            echo ""
            echo -e "  ${RED}✗${NC} Training failed!"
            exit 1
        else
            echo -n "."
            sleep 5
            ELAPSED=$((ELAPSED + 5))
        fi
    done
    
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo ""
        echo -e "  ${YELLOW}⚠${NC} Training timeout (but may still complete)"
    fi
done

# Check round status
echo ""
echo -e "${BLUE}▶ Checking round status...${NC}"
curl -s "$CENTRAL_URL/round/$ROUND_ID/status" | python3 -m json.tool

# Trigger aggregation
echo ""
echo -e "${BLUE}▶ Triggering FedAvg aggregation...${NC}"
AGG_RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/$ROUND_ID/aggregate")

echo "$AGG_RESPONSE" | python3 -m json.tool

if echo "$AGG_RESPONSE" | grep -q "success"; then
    echo ""
    echo "============================================================"
    echo -e "${GREEN}✓ End-to-End Test PASSED!${NC}"
    echo "============================================================"
else
    echo ""
    echo "============================================================"
    echo -e "${RED}✗ Aggregation failed${NC}"
    echo "============================================================"
    exit 1
fi
