#!/bin/bash
# Test Flower FL Workflow
# This script tests the complete Flower integration

set -e  # Exit on error

echo "========================================================================"
echo "FLOWER FL WORKFLOW TEST"
echo "========================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CENTRAL_URL="http://localhost:8081"
NODE1_URL="http://localhost:8001"
NODE2_URL="http://localhost:8002"
NODE3_URL="http://localhost:8003"
ROUND_ID="R-FLOWER-TEST-$(date +%s)"

echo "Configuration:"
echo "  - Central URL: $CENTRAL_URL"
echo "  - Round ID: $ROUND_ID"
echo ""

# Function to check service health
check_service() {
    local name=$1
    local url=$2
    
    echo -n "Checking $name... "
    
    if curl -s "$url/health" > /dev/null 2>&1 || curl -s "$url/api/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        return 1
    fi
}

# Step 1: Check all services
echo "▶ Step 1: Checking services..."
check_service "Central" "$CENTRAL_URL" || exit 1
check_service "Node1" "$NODE1_URL" || exit 1
check_service "Node2" "$NODE2_URL" || exit 1
check_service "Node3" "$NODE3_URL" || exit 1
echo ""

# Step 2: Check if datasets exist
echo "▶ Step 2: Checking datasets..."
for i in 1 2 3; do
    NODE_URL="http://localhost:800$i"
    echo -n "  Node$i datasets... "
    
    DATASETS=$(curl -s "$NODE_URL/api/data/list" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    
    if [ "$DATASETS" -gt 0 ]; then
        echo -e "${GREEN}✓ $DATASETS dataset(s)${NC}"
    else
        echo -e "${YELLOW}⚠ No datasets (upload needed)${NC}"
    fi
done
echo ""

# Step 3: Create FL round on central
echo "▶ Step 3: Creating FL round..."
CREATE_RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/create" \
    -H "Content-Type: application/json" \
    -d "{
        \"round_id\": \"$ROUND_ID\",
        \"model_name\": \"resnet18\",
        \"num_classes\": 2,
        \"pretrained\": true,
        \"hyperparameters\": {
            \"num_epochs\": 2,
            \"batch_size\": 16,
            \"learning_rate\": 0.001,
            \"optimizer\": \"adam\"
        }
    }")

if echo "$CREATE_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ Round created: $ROUND_ID${NC}"
else
    echo -e "${RED}✗ Failed to create round${NC}"
    echo "$CREATE_RESPONSE"
    exit 1
fi
echo ""

# Step 4: Nodes join round
echo "▶ Step 4: Nodes joining round..."
for i in 1 2 3; do
    NODE_URL="http://localhost:800$i"
    echo -n "  Node$i joining... "
    
    JOIN_RESPONSE=$(curl -s -X POST "$NODE_URL/api/federated/join/$ROUND_ID" \
        -H "Content-Type: application/json" \
        -d "{\"node_id\": \"node$i\"}")
    
    if echo "$JOIN_RESPONSE" | grep -q "success"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
done
echo ""

# Step 5: Check round status
echo "▶ Step 5: Checking round status..."
STATUS_RESPONSE=$(curl -s "$CENTRAL_URL/round/$ROUND_ID/status")
echo "$STATUS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$STATUS_RESPONSE"
echo ""

# Step 6: Instructions for manual Flower server start
echo "========================================================================"
echo "MANUAL STEPS REQUIRED"
echo "========================================================================"
echo ""
echo "To complete the FL workflow with Flower:"
echo ""
echo "1. Start Flower server (in a new terminal):"
echo "   ${YELLOW}docker compose exec central python -m app.flower_server${NC}"
echo ""
echo "2. Start Flower clients on each node (in separate terminals):"
echo "   ${YELLOW}# Get dataset IDs first:${NC}"
echo "   curl http://localhost:8001/api/data/list"
echo "   curl http://localhost:8002/api/data/list"
echo "   curl http://localhost:8003/api/data/list"
echo ""
echo "   ${YELLOW}# Then start training with dataset IDs:${NC}"
echo "   curl -X POST \"http://localhost:8001/api/federated/train/$ROUND_ID?dataset_id=<DATASET_ID>\""
echo "   curl -X POST \"http://localhost:8002/api/federated/train/$ROUND_ID?dataset_id=<DATASET_ID>\""
echo "   curl -X POST \"http://localhost:8003/api/federated/train/$ROUND_ID?dataset_id=<DATASET_ID>\""
echo ""
echo "3. Monitor progress:"
echo "   - Check Flower server logs"
echo "   - Check worker logs: docker compose logs -f node1-worker"
echo ""
echo "4. After completion, check results:"
echo "   curl $CENTRAL_URL/round/$ROUND_ID/status"
echo "   ls -la storage/central/models/"
echo ""
echo "========================================================================"
echo ""

# Step 7: Summary
echo "▶ Summary:"
echo "  - Round ID: ${GREEN}$ROUND_ID${NC}"
echo "  - Status: ${YELLOW}Ready for Flower training${NC}"
echo "  - Next: Start Flower server and clients (see instructions above)"
echo ""
echo "========================================================================"
