#!/bin/bash
# Script pentru testarea Central FL Server

set -e

CENTRAL_URL="http://localhost:8080"

echo "=========================================="
echo "Testing Central FL Server"
echo "URL: ${CENTRAL_URL}"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test function
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    
    echo -n "Testing ${name}... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "${CENTRAL_URL}${endpoint}")
    else
        response=$(curl -s -w "\n%{http_code}" -X ${method} "${CENTRAL_URL}${endpoint}" \
            -H "Content-Type: application/json" \
            -d "${data}")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "${GREEN}✓ OK${NC} (HTTP ${http_code})"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
        echo ""
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP ${http_code})"
        echo "$body"
        echo ""
        return 1
    fi
}

# Wait for Central to be ready
echo "Waiting for Central server to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s "${CENTRAL_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Central server is ready${NC}"
        echo ""
        break
    fi
    attempt=$((attempt + 1))
    echo -n "."
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗ Central server failed to start${NC}"
    exit 1
fi

# Test 1: Health Check
echo "=========================================="
echo "Test 1: Health Check"
echo "=========================================="
test_endpoint "Health Check" "GET" "/health"

# Test 2: Create Round
echo "=========================================="
echo "Test 2: Create FL Round"
echo "=========================================="
test_endpoint "Create Round R-1" "POST" "/round/create" '{
    "round_id": "R-1",
    "model_name": "resnet18",
    "num_classes": 2,
    "pretrained": true,
    "hyperparameters": {
        "num_epochs": 5,
        "batch_size": 32,
        "learning_rate": 0.001,
        "optimizer": "adam"
    }
}'

# Test 3: Get Round Plan
echo "=========================================="
echo "Test 3: Get Round Plan"
echo "=========================================="
test_endpoint "Get Round Plan" "GET" "/round/R-1/plan"

# Test 4: Node Join Round
echo "=========================================="
echo "Test 4: Nodes Join Round"
echo "=========================================="
test_endpoint "Node1 Join" "POST" "/round/R-1/join" '{
    "node_id": "node1"
}'

test_endpoint "Node2 Join" "POST" "/round/R-1/join" '{
    "node_id": "node2"
}'

test_endpoint "Node3 Join" "POST" "/round/R-1/join" '{
    "node_id": "node3"
}'

# Test 5: Get Round Status
echo "=========================================="
echo "Test 5: Get Round Status"
echo "=========================================="
test_endpoint "Round Status" "GET" "/round/R-1/status"

# Test 6: Get Global Model
echo "=========================================="
echo "Test 6: Get Global Model"
echo "=========================================="
echo -e "${YELLOW}Note: This will return a large base64-encoded model${NC}"
echo ""
curl -s "${CENTRAL_URL}/model/global/R-1" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Round ID: {data['round_id']}\")
print(f\"Model: {data['model_name']}\")
print(f\"Hash: {data['hash'][:32]}...\")
print(f\"State dict size: {len(data['state_dict'])} chars\")
"
echo ""

# Test 7: List Rounds
echo "=========================================="
echo "Test 7: List All Rounds"
echo "=========================================="
test_endpoint "List Rounds" "GET" "/rounds/list"

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}✓ Basic endpoints are working${NC}"
echo -e "${YELLOW}⚠ Full FL workflow requires:${NC}"
echo "  - Nodes to submit updates"
echo "  - Aggregation trigger"
echo ""
echo "Next steps:"
echo "  1. Nodes pull model: curl ${CENTRAL_URL}/model/global/R-1"
echo "  2. Nodes train locally and submit updates"
echo "  3. Trigger aggregation: curl -X POST ${CENTRAL_URL}/round/R-1/aggregate"
echo "  4. Get results: curl ${CENTRAL_URL}/round/R-1/results"
echo ""
