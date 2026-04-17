#!/bin/bash
# End-to-End FL Workflow Test Script
# Tests complete federated learning round with 3 nodes

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CENTRAL_URL="http://localhost:8080"
NODE1_URL="http://localhost:8001"
NODE2_URL="http://localhost:8002"
NODE3_URL="http://localhost:8003"
ROUND_ID="R-TEST-$(date +%s)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Fed-Med-FL End-to-End Workflow Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print step
step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

# Function to print success
success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error
error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

# Function to wait for user
wait_user() {
    echo -e "${YELLOW}Press ENTER to continue...${NC}"
    read
}

# ============================================================================
# Step 0: Check services
# ============================================================================
step "Step 0: Checking services..."

curl -s $CENTRAL_URL/health > /dev/null || error "Central server not responding"
success "Central server OK"

curl -s $NODE1_URL/api/health > /dev/null || error "Node1 not responding"
success "Node1 OK"

curl -s $NODE2_URL/api/health > /dev/null || error "Node2 not responding"
success "Node2 OK"

curl -s $NODE3_URL/api/health > /dev/null || error "Node3 not responding"
success "Node3 OK"

echo ""

# ============================================================================
# Step 1: Create test datasets
# ============================================================================
step "Step 1: Creating test datasets..."

if [ ! -f "test_dataset_node1.zip" ]; then
    echo "Creating synthetic datasets..."
    python3 scripts/create_test_dataset.py || error "Failed to create datasets"
else
    echo "Test datasets already exist, skipping creation"
fi

success "Test datasets ready"
echo ""

# ============================================================================
# Step 2: Upload datasets to nodes
# ============================================================================
step "Step 2: Uploading datasets to nodes..."

echo "⚠️  MANUAL STEP REQUIRED:"
echo "   1. Open http://localhost:3001 (Node1)"
echo "   2. Go to 'Studies' page"
echo "   3. Upload 'test_dataset_node1.zip' with split='train'"
echo "   4. Note the dataset_id (e.g., dataset_train_abc123)"
echo ""
echo "   Repeat for Node2 (port 3002) and Node3 (port 3003)"
echo ""
echo "   OR use curl (if you have the files):"
echo "   curl -X POST $NODE1_URL/api/data/upload -F 'file=@test_dataset_node1.zip' -F 'split=train'"
echo ""

wait_user

# Ask for dataset IDs
echo "Enter dataset IDs:"
read -p "Node1 dataset_id: " DATASET1
read -p "Node2 dataset_id: " DATASET2
read -p "Node3 dataset_id: " DATASET3

success "Datasets uploaded"
echo ""

# ============================================================================
# Step 3: Create FL Round
# ============================================================================
step "Step 3: Creating FL round $ROUND_ID..."

RESPONSE=$(curl -s -X POST $CENTRAL_URL/round/create \
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

echo "$RESPONSE" | python3 -m json.tool

if echo "$RESPONSE" | grep -q "success"; then
    success "Round created: $ROUND_ID"
else
    error "Failed to create round"
fi

echo ""

# ============================================================================
# Step 4: Nodes join round
# ============================================================================
step "Step 4: Nodes joining round..."

# Node1
RESPONSE=$(curl -s -X POST $CENTRAL_URL/round/$ROUND_ID/join \
  -H "Content-Type: application/json" \
  -d '{"node_id": "node1"}')

if echo "$RESPONSE" | grep -q "success"; then
    success "Node1 joined"
else
    error "Node1 failed to join"
fi

# Node2
RESPONSE=$(curl -s -X POST $CENTRAL_URL/round/$ROUND_ID/join \
  -H "Content-Type: application/json" \
  -d '{"node_id": "node2"}')

if echo "$RESPONSE" | grep -q "success"; then
    success "Node2 joined"
else
    error "Node2 failed to join"
fi

# Node3
RESPONSE=$(curl -s -X POST $CENTRAL_URL/round/$ROUND_ID/join \
  -H "Content-Type: application/json" \
  -d '{"node_id": "node3"}')

if echo "$RESPONSE" | grep -q "success"; then
    success "Node3 joined"
else
    error "Node3 failed to join"
fi

echo ""

# ============================================================================
# Step 5: Check round status
# ============================================================================
step "Step 5: Checking round status..."

RESPONSE=$(curl -s $CENTRAL_URL/round/$ROUND_ID/status)
echo "$RESPONSE" | python3 -m json.tool

NUM_PARTICIPANTS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['num_participants'])")

if [ "$NUM_PARTICIPANTS" -eq 3 ]; then
    success "All 3 nodes registered"
else
    error "Expected 3 participants, got $NUM_PARTICIPANTS"
fi

echo ""

# ============================================================================
# Step 6: Start federated training on all nodes
# ============================================================================
step "Step 6: Starting federated training..."

echo "Starting training on Node1..."
RESPONSE=$(curl -s -X POST "$NODE1_URL/api/federated/train/$ROUND_ID?dataset_id=$DATASET1" \
  -H "Content-Type: application/json")
JOB1=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
success "Node1 training started: $JOB1"

echo "Starting training on Node2..."
RESPONSE=$(curl -s -X POST "$NODE2_URL/api/federated/train/$ROUND_ID?dataset_id=$DATASET2" \
  -H "Content-Type: application/json")
JOB2=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
success "Node2 training started: $JOB2"

echo "Starting training on Node3..."
RESPONSE=$(curl -s -X POST "$NODE3_URL/api/federated/train/$ROUND_ID?dataset_id=$DATASET3" \
  -H "Content-Type: application/json")
JOB3=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
success "Node3 training started: $JOB3"

echo ""

# ============================================================================
# Step 7: Monitor training progress
# ============================================================================
step "Step 7: Monitoring training progress..."

echo "Waiting for all nodes to complete training..."
echo "(This may take 5-15 minutes depending on hardware)"
echo ""

check_job_status() {
    local NODE_URL=$1
    local JOB_ID=$2
    curl -s "$NODE_URL/api/train/status/$JOB_ID" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown"
}

while true; do
    STATUS1=$(check_job_status $NODE1_URL $JOB1)
    STATUS2=$(check_job_status $NODE2_URL $JOB2)
    STATUS3=$(check_job_status $NODE3_URL $JOB3)
    
    echo -ne "\rNode1: $STATUS1 | Node2: $STATUS2 | Node3: $STATUS3    "
    
    # Check if all completed or failed
    if [ "$STATUS1" = "completed" ] && [ "$STATUS2" = "completed" ] && [ "$STATUS3" = "completed" ]; then
        echo ""
        success "All nodes completed training!"
        break
    fi
    
    if [ "$STATUS1" = "failed" ] || [ "$STATUS2" = "failed" ] || [ "$STATUS3" = "failed" ]; then
        echo ""
        error "One or more nodes failed training"
    fi
    
    sleep 5
done

echo ""

# ============================================================================
# Step 8: Check updates received
# ============================================================================
step "Step 8: Checking updates received by central..."

RESPONSE=$(curl -s $CENTRAL_URL/round/$ROUND_ID/status)
echo "$RESPONSE" | python3 -m json.tool

UPDATES_RECEIVED=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['updates_received'])")

if [ "$UPDATES_RECEIVED" -eq 3 ]; then
    success "All 3 updates received"
else
    echo "⚠️  Expected 3 updates, got $UPDATES_RECEIVED"
    echo "Waiting 10 more seconds..."
    sleep 10
    
    RESPONSE=$(curl -s $CENTRAL_URL/round/$ROUND_ID/status)
    UPDATES_RECEIVED=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['updates_received'])")
    
    if [ "$UPDATES_RECEIVED" -eq 3 ]; then
        success "All 3 updates received"
    else
        error "Still missing updates: $UPDATES_RECEIVED/3"
    fi
fi

echo ""

# ============================================================================
# Step 9: Trigger aggregation
# ============================================================================
step "Step 9: Triggering FedAvg aggregation..."

RESPONSE=$(curl -s -X POST "$CENTRAL_URL/round/$ROUND_ID/aggregate")
echo "$RESPONSE" | python3 -m json.tool

if echo "$RESPONSE" | grep -q "success"; then
    success "Aggregation completed!"
else
    error "Aggregation failed"
fi

echo ""

# ============================================================================
# Step 10: Get final results
# ============================================================================
step "Step 10: Getting final results..."

RESPONSE=$(curl -s $CENTRAL_URL/round/$ROUND_ID/results)
echo "$RESPONSE" | python3 -m json.tool

success "Results retrieved"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ End-to-End Test PASSED!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Round ID: $ROUND_ID"
echo "View results at: $CENTRAL_URL/round/$ROUND_ID/results"
echo ""
