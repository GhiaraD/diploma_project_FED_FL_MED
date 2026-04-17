#!/bin/bash
# Demo End-to-End Federated Learning Workflow
# 
# Demonstrează un ciclu complet FL:
# 1. Central creează rundă
# 2. 3 noduri se înscriu
# 3. Noduri download model global
# 4. Noduri antrenează local (simulat cu dataset dummy)
# 5. Noduri trimit updates
# 6. Central agregă
# 7. Afișare rezultate

set -e

CENTRAL_URL="http://localhost:8080"
NODE1_URL="http://localhost:8001"
NODE2_URL="http://localhost:8002"
NODE3_URL="http://localhost:8003"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=========================================="
echo "Federated Learning Workflow Demo"
echo "=========================================="
echo ""

# Check if services are running
echo -e "${BLUE}Checking services...${NC}"
for url in $CENTRAL_URL $NODE1_URL $NODE2_URL $NODE3_URL; do
    if curl -s "${url}/api/health" > /dev/null 2>&1 || curl -s "${url}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} ${url} is running"
    else
        echo -e "${RED}✗${NC} ${url} is NOT running"
        echo ""
        echo "Please start all services first:"
        echo "  docker compose up -d central node1-api node1-worker node1-redis node2-api node2-worker node2-redis node3-api node3-worker node3-redis"
        exit 1
    fi
done
echo ""

# Step 1: Central creates round
echo "=========================================="
echo -e "${CYAN}Step 1: Central creates FL round${NC}"
echo "=========================================="
echo ""

ROUND_ID="R-DEMO-$(date +%s)"

create_response=$(curl -s -X POST "${CENTRAL_URL}/round/create" \
    -H "Content-Type: application/json" \
    -d "{
        \"round_id\": \"${ROUND_ID}\",
        \"model_name\": \"resnet18\",
        \"num_classes\": 2,
        \"pretrained\": true,
        \"hyperparameters\": {
            \"num_epochs\": 2,
            \"batch_size\": 8,
            \"learning_rate\": 0.001,
            \"optimizer\": \"adam\"
        }
    }")

echo "$create_response" | python3 -m json.tool
echo ""

base_model_hash=$(echo "$create_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['base_model_hash'])")
echo -e "${GREEN}✓ Round created: ${ROUND_ID}${NC}"
echo -e "${GREEN}✓ Base model hash: ${base_model_hash:0:16}...${NC}"
echo ""

# Step 2: Nodes join round
echo "=========================================="
echo -e "${CYAN}Step 2: Nodes join round${NC}"
echo "=========================================="
echo ""

for node_id in node1 node2 node3; do
    node_url_var="NODE${node_id#node}_URL"
    node_url=${!node_url_var}
    
    join_response=$(curl -s -X POST "${CENTRAL_URL}/round/${ROUND_ID}/join" \
        -H "Content-Type: application/json" \
        -d "{\"node_id\": \"${node_id}\"}")
    
    echo -e "${GREEN}✓${NC} ${node_id} joined round"
done
echo ""

# Step 3: Get round status
echo "=========================================="
echo -e "${CYAN}Step 3: Round status${NC}"
echo "=========================================="
echo ""

status_response=$(curl -s "${CENTRAL_URL}/round/${ROUND_ID}/status")
echo "$status_response" | python3 -m json.tool
echo ""

# Step 4: Nodes get round plan
echo "=========================================="
echo -e "${CYAN}Step 4: Nodes get training plan${NC}"
echo "=========================================="
echo ""

plan_response=$(curl -s "${CENTRAL_URL}/round/${ROUND_ID}/plan")
echo "$plan_response" | python3 -m json.tool
echo ""

# Step 5: Simulate node training and updates
echo "=========================================="
echo -e "${CYAN}Step 5: Nodes train and submit updates${NC}"
echo "=========================================="
echo ""
echo -e "${YELLOW}Note: This is a simulation. In real workflow:${NC}"
echo "  1. Nodes would download global model"
echo "  2. Train on local datasets"
echo "  3. Compute delta = W_local - W_global"
echo "  4. Submit delta + metrics to central"
echo ""
echo -e "${YELLOW}For now, we'll skip this step as it requires:${NC}"
echo "  - Real datasets on each node"
echo "  - Actual training (takes time)"
echo "  - Delta computation"
echo ""
echo -e "${BLUE}To test the full workflow manually:${NC}"
echo ""
echo "1. Upload dataset to node1:"
echo "   curl -X POST ${NODE1_URL}/api/data/upload -F 'file=@dataset.zip' -F 'split=train'"
echo ""
echo "2. Start federated training on node1:"
echo "   curl -X POST ${NODE1_URL}/api/federated/train/${ROUND_ID}?dataset_id=<dataset_id>"
echo ""
echo "3. Repeat for node2 and node3"
echo ""
echo "4. Wait for all nodes to complete training"
echo ""
echo "5. Trigger aggregation:"
echo "   curl -X POST ${CENTRAL_URL}/round/${ROUND_ID}/aggregate"
echo ""
echo "6. Get results:"
echo "   curl ${CENTRAL_URL}/round/${ROUND_ID}/results"
echo ""

# Summary
echo "=========================================="
echo -e "${CYAN}Demo Summary${NC}"
echo "=========================================="
echo ""
echo -e "${GREEN}✓ Central Server:${NC} Round ${ROUND_ID} created"
echo -e "${GREEN}✓ Participants:${NC} node1, node2, node3 joined"
echo -e "${GREEN}✓ Model:${NC} ResNet18 pretrained initialized"
echo -e "${GREEN}✓ Hyperparameters:${NC} 2 epochs, batch_size=8, lr=0.001"
echo ""
echo -e "${YELLOW}⚠ Next steps require:${NC}"
echo "  - Datasets uploaded to nodes"
echo "  - Actual training execution"
echo "  - Delta submission"
echo "  - Aggregation trigger"
echo ""
echo -e "${BLUE}See docs/PHASE4_COMPLETE.md for full workflow details${NC}"
echo ""
