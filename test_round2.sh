#!/bin/bash
# Round 2 - Continue FL training from Round 1 aggregated model

set -e

CENTRAL_URL="http://localhost:8080"
ROUND1_ID="R-2NODES-1776623349"
ROUND2_ID="R-2NODES-ROUND2-$(date +%s)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "============================================================"
echo "FL Round 2 - Continuing from Round 1"
echo "============================================================"
echo "Round 1 ID: $ROUND1_ID"
echo "Round 2 ID: $ROUND2_ID"
echo ""

# Step 1: Get Round 1 results
echo -e "${BLUE}▶ Step 1: Getting Round 1 results...${NC}"
ROUND1_RESULTS=$(curl -s "$CENTRAL_URL/round/$ROUND1_ID/results")
echo "$ROUND1_RESULTS" | python3 -m json.tool

ROUND1_METRICS=$(echo "$ROUND1_RESULTS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
metrics = data.get('aggregated_metrics', {})
print(f\"Round 1 Metrics:\")
print(f\"  Accuracy: {metrics.get('accuracy', 0):.4f}\")
print(f\"  F1 Score: {metrics.get('f1', 0):.4f}\")
print(f\"  AUC: {metrics.get('auc', 0):.4f}\")
" 2>/dev/null || echo "Could not parse Round 1 metrics")

echo ""
echo "$ROUND1_METRICS"

# Step 2: Create Round 2 using aggregated model from Round 1
echo ""
echo -e "${BLUE}▶ Step 2: Creating Round 2 with aggregated model from Round 1...${NC}"

# Get the aggregated model path from Round 1
AGGREGATED_MODEL_PATH="/storage/models/global_${ROUND1_ID}_aggregated.pt"
echo "  Using model: $AGGREGATED_MODEL_PATH"

# Note: We need to manually copy the aggregated model to be the base for Round 2
# This is done inside the central container
echo "  Preparing base model for Round 2..."
docker compose exec -T central cp "$AGGREGATED_MODEL_PATH" "/storage/models/base_${ROUND2_ID}.pt" 2>/dev/null || echo "  (Model will be created during round creation)"

CREATE_RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/create" \
  -H 'Content-Type: application/json' \
  -d '{
    "round_id": "'"$ROUND2_ID"'",
    "model_name": "resnet18",
    "num_classes": 2,
    "pretrained": false,
    "hyperparameters": {
      "num_epochs": 1,
      "batch_size": 16,
      "learning_rate": 0.001,
      "optimizer": "adam"
    }
  }')

if echo "$CREATE_RESPONSE" | grep -q "success"; then
    echo -e "  ${GREEN}✓${NC} Round 2 created"
    echo "  Hyperparameters: 1 epoch, batch_size=16"
else
    echo -e "  ${YELLOW}⚠${NC} Round created (will use pretrained model as fallback)"
fi

# Step 3: Manually replace base model with Round 1 aggregated model
echo ""
echo -e "${BLUE}▶ Step 3: Replacing base model with Round 1 aggregated model...${NC}"
docker compose exec -T central bash -c "
if [ -f '$AGGREGATED_MODEL_PATH' ]; then
    cp '$AGGREGATED_MODEL_PATH' '/storage/models/base_${ROUND2_ID}.pt'
    echo '  ✓ Base model replaced with Round 1 aggregated model'
else
    echo '  ✗ Round 1 aggregated model not found!'
    exit 1
fi
"

# Step 4: Register nodes
echo ""
echo -e "${BLUE}▶ Step 4: Registering nodes...${NC}"
for node in node1 node2; do
    JOIN_RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/$ROUND2_ID/join" \
      -H 'Content-Type: application/json' \
      -d "{\"node_id\": \"$node\", \"node_url\": \"http://$node-api:8000\"}")
    
    if echo "$JOIN_RESPONSE" | grep -q "success"; then
        echo -e "  ${GREEN}✓${NC} $node joined"
    else
        echo -e "  ${YELLOW}⚠${NC} $node join status unclear"
    fi
done

# Step 5: Train nodes sequentially
echo ""
echo -e "${BLUE}▶ Step 5: Training nodes sequentially (Round 2)...${NC}"
echo ""

for node_num in 1 2; do
    node="node$node_num"
    port=$((8000 + node_num))
    
    echo -e "${CYAN}━━━ Training $node (Round 2) ━━━${NC}"
    
    DATASET_ID=$(curl -s "http://localhost:$port/api/data/list" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['dataset_id'])")
    echo "  Dataset ID: $DATASET_ID"
    
    TRAIN_RESPONSE=$(curl -s -X POST "http://localhost:$port/api/federated/train/$ROUND2_ID?dataset_id=$DATASET_ID")
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
            echo -e "  ${YELLOW}⚠${NC} Training failed!"
            break
        else
            echo -n "."
            sleep 5
            ELAPSED=$((ELAPSED + 5))
        fi
    done
    
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo ""
        echo -e "  ${YELLOW}⚠${NC} Training timeout"
    fi
    
    echo ""
done

# Step 6: Check round status
echo ""
echo -e "${BLUE}▶ Step 6: Checking Round 2 status...${NC}"
curl -s "$CENTRAL_URL/round/$ROUND2_ID/status" | python3 -m json.tool

# Step 7: Trigger aggregation
echo ""
echo -e "${BLUE}▶ Step 7: Triggering FedAvg aggregation (Round 2)...${NC}"
AGG_RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/$ROUND2_ID/aggregate")

echo "$AGG_RESPONSE" | python3 -m json.tool

# Step 8: Compare results
echo ""
echo "============================================================"
echo "COMPARISON: Round 1 vs Round 2"
echo "============================================================"

echo "$AGG_RESPONSE" | python3 -c "
import sys, json

try:
    round2_data = json.load(sys.stdin)
    round2_metrics = round2_data.get('aggregated_metrics', {})
    
    # Round 1 metrics (from earlier)
    round1_metrics = {
        'accuracy': 0.9209770114942528,
        'f1': 0.9448670252679636,
        'auc': 0.9831758341820747
    }
    
    print('Metric          Round 1    Round 2    Improvement')
    print('=' * 55)
    
    for metric in ['accuracy', 'f1', 'auc']:
        r1 = round1_metrics.get(metric, 0)
        r2 = round2_metrics.get(metric, 0)
        diff = r2 - r1
        sign = '+' if diff > 0 else ''
        print(f'{metric:12s}    {r1:.4f}     {r2:.4f}     {sign}{diff:.4f}')
    
    print('=' * 55)
    
    if round2_data.get('status') == 'success':
        print('\\n✓ Round 2 completed successfully!')
    else:
        print('\\n✗ Round 2 aggregation failed')
        
except Exception as e:
    print(f'Could not compare results: {e}')
"

echo ""
echo "============================================================"
