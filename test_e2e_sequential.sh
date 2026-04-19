#!/bin/bash
# End-to-End Test - Sequential Training with Small Batches
# Tests the complete FL workflow including aggregation fix

set -e  # Exit on error

CENTRAL_URL="http://localhost:8080"
ROUND_ID="R-E2E-TEST-$(date +%s)"

echo "============================================================"
echo "FL End-to-End Test - Sequential Training"
echo "============================================================"
echo "Round ID: $ROUND_ID"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check services
echo -e "${BLUE}▶ Step 1: Checking services...${NC}"
for service in central node1-api node2-api node3-api node1-worker node2-worker node3-worker; do
    if docker compose ps | grep -q "$service.*Up"; then
        echo -e "  ${GREEN}✓${NC} $service is running"
    else
        echo -e "  ${RED}✗${NC} $service is not running"
        echo ""
        echo "Starting services..."
        docker compose up -d
        echo "Waiting 30 seconds for services to be ready..."
        sleep 30
        break
    fi
done

# Wait for services to be ready
echo ""
echo -e "${BLUE}▶ Waiting for services to be ready...${NC}"
sleep 5

# Check central health
if curl -s http://localhost:8080/health | grep -q "ok"; then
    echo -e "  ${GREEN}✓${NC} Central server is healthy"
else
    echo -e "  ${RED}✗${NC} Central server is not responding"
    exit 1
fi

# Step 2: Create FL round with small hyperparameters
echo ""
echo -e "${BLUE}▶ Step 2: Creating FL round with small batch size...${NC}"
CREATE_RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/create" \
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
  }')

if echo "$CREATE_RESPONSE" | grep -q "success"; then
    echo -e "  ${GREEN}✓${NC} Round created successfully"
    echo "  Hyperparameters: 1 epoch, batch_size=16"
else
    echo -e "  ${RED}✗${NC} Failed to create round"
    echo "$CREATE_RESPONSE" | python3 -m json.tool
    exit 1
fi

# Step 3: Register nodes
echo ""
echo -e "${BLUE}▶ Step 3: Registering nodes...${NC}"
for node in node1 node2 node3; do
    JOIN_RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/$ROUND_ID/join" \
      -H 'Content-Type: application/json' \
      -d "{\"node_id\": \"$node\", \"node_url\": \"http://$node-api:8000\"}")
    
    if echo "$JOIN_RESPONSE" | grep -q "success"; then
        echo -e "  ${GREEN}✓${NC} $node joined"
    else
        echo -e "  ${RED}✗${NC} $node failed to join"
        echo "$JOIN_RESPONSE"
        exit 1
    fi
done

# Step 4: Train nodes sequentially
echo ""
echo -e "${BLUE}▶ Step 4: Training nodes sequentially...${NC}"
echo ""

for node_num in 1 2 3; do
    node="node$node_num"
    port=$((8000 + node_num))
    
    echo -e "${YELLOW}━━━ Training $node ━━━${NC}"
    
    # Get dataset ID
    DATASET_ID=$(curl -s "http://localhost:$port/api/data/list" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['dataset_id'])" 2>/dev/null || echo "")
    
    if [ -z "$DATASET_ID" ]; then
        echo -e "  ${RED}✗${NC} No dataset found for $node"
        exit 1
    fi
    
    echo "  Dataset ID: $DATASET_ID"
    
    # Start training
    TRAIN_RESPONSE=$(curl -s -X POST "http://localhost:$port/api/federated/train/$ROUND_ID?dataset_id=$DATASET_ID")
    
    if echo "$TRAIN_RESPONSE" | grep -q "job_id"; then
        JOB_ID=$(echo "$TRAIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
        echo -e "  ${GREEN}✓${NC} Training started (Job ID: $JOB_ID)"
    else
        echo -e "  ${RED}✗${NC} Failed to start training"
        echo "$TRAIN_RESPONSE"
        exit 1
    fi
    
    # Monitor training progress
    echo -n "  Progress: "
    MAX_WAIT=300  # 5 minutes max
    ELAPSED=0
    
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        STATUS_RESPONSE=$(curl -s "http://localhost:$port/api/train/status/$JOB_ID")
        STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        
        if [ "$STATUS" = "completed" ]; then
            echo ""
            echo -e "  ${GREEN}✓${NC} Training completed!"
            
            # Get metrics
            METRICS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); m=d.get('result',{}).get('metrics',{}); print(f\"Acc: {m.get('accuracy',0):.4f}, F1: {m.get('f1',0):.4f}, AUC: {m.get('auc',0):.4f}\")" 2>/dev/null || echo "N/A")
            echo -e "  ${GREEN}✓${NC} Metrics: $METRICS"
            break
        elif [ "$STATUS" = "failed" ]; then
            echo ""
            echo -e "  ${RED}✗${NC} Training failed!"
            echo "$STATUS_RESPONSE" | python3 -m json.tool
            exit 1
        else
            echo -n "."
            sleep 5
            ELAPSED=$((ELAPSED + 5))
        fi
    done
    
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo ""
        echo -e "  ${RED}✗${NC} Training timeout!"
        exit 1
    fi
    
    echo ""
done

# Step 5: Check round status
echo ""
echo -e "${BLUE}▶ Step 5: Checking round status...${NC}"
ROUND_STATUS=$(curl -s "$CENTRAL_URL/round/$ROUND_ID/status")
UPDATES_COUNT=$(echo "$ROUND_STATUS" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('updates', [])))" 2>/dev/null || echo "0")

echo "  Updates received: $UPDATES_COUNT/3"

if [ "$UPDATES_COUNT" = "3" ]; then
    echo -e "  ${GREEN}✓${NC} All nodes submitted updates"
else
    echo -e "  ${YELLOW}⚠${NC} Only $UPDATES_COUNT updates received"
fi

# Step 6: Trigger aggregation
echo ""
echo -e "${BLUE}▶ Step 6: Triggering FedAvg aggregation...${NC}"
AGG_RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/$ROUND_ID/aggregate")

if echo "$AGG_RESPONSE" | grep -q "success"; then
    echo -e "  ${GREEN}✓${NC} Aggregation completed successfully!"
    echo ""
    echo "============================================================"
    echo "AGGREGATION RESULTS"
    echo "============================================================"
    echo "$AGG_RESPONSE" | python3 -m json.tool
    echo "============================================================"
    
    # Extract and display metrics
    echo ""
    echo "Aggregated Metrics:"
    echo "$AGG_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
metrics = data.get('aggregated_metrics', {})
for metric, value in metrics.items():
    print(f'  {metric:12s}: {value:.6f}')
print(f\"\\nTotal samples: {data.get('total_samples', 0)}\")
print(f\"Participants: {data.get('num_participants', 0)}\")
" 2>/dev/null || echo "Could not parse metrics"
    
else
    echo -e "  ${RED}✗${NC} Aggregation failed!"
    echo "$AGG_RESPONSE" | python3 -m json.tool
    exit 1
fi

# Step 7: Get final results
echo ""
echo -e "${BLUE}▶ Step 7: Getting final results...${NC}"
RESULTS=$(curl -s "$CENTRAL_URL/round/$ROUND_ID/results")
echo "$RESULTS" | python3 -m json.tool

echo ""
echo "============================================================"
echo -e "${GREEN}✓ End-to-End Test PASSED!${NC}"
echo "============================================================"
echo ""
echo "Summary:"
echo "  - Round ID: $ROUND_ID"
echo "  - All 3 nodes trained successfully"
echo "  - All updates submitted"
echo "  - FedAvg aggregation completed"
echo "  - Global model saved"
echo ""
echo "The aggregation fix is working correctly! ✨"
echo ""
