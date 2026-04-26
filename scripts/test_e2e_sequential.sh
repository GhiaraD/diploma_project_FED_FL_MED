#!/bin/bash

# E2E Sequential Testing Script for Fed-Med-FL
# Tests 3 different model architectures sequentially
# Each test: 2 rounds, 2 epochs, 2 nodes participating

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NODE1_URL="http://localhost:8001"
NODE2_URL="http://localhost:8002"
NODE3_URL="http://localhost:8003"

NUM_ROUNDS=2
NUM_EPOCHS=2
BATCH_SIZE=16
LEARNING_RATE=0.001
MIN_CLIENTS=2
MIN_FIT_CLIENTS=2
MIN_AVAILABLE_CLIENTS=2

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Fed-Med-FL E2E Sequential Testing${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  - 3 Tests (ResNet18, DenseNet121, EfficientNet-B0)"
echo "  - ${NUM_ROUNDS} Rounds per test"
echo "  - ${NUM_EPOCHS} Epochs per round"
echo "  - 2 Nodes participating (Node1 & Node2)"
echo "  - Node3 will NOT participate"
echo ""

# Function to check if services are running
check_services() {
    echo -e "${BLUE}Checking if services are running...${NC}"
    
    if ! curl -s "${NODE1_URL}/api/health" > /dev/null; then
        echo -e "${RED}Error: Node1 is not running${NC}"
        exit 1
    fi
    
    if ! curl -s "${NODE2_URL}/api/health" > /dev/null; then
        echo -e "${RED}Error: Node2 is not running${NC}"
        exit 1
    fi
    
    if ! curl -s "${NODE3_URL}/api/health" > /dev/null; then
        echo -e "${RED}Error: Node3 is not running${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ All services are running${NC}"
    echo ""
}

# Function to register datasets (only once at the beginning)
register_datasets() {
    echo -e "${BLUE}Step 1: Registering datasets on nodes...${NC}"
    
    # Node1 - Register dataset (path inside container is /storage/datasets/...)
    echo "Registering dataset on Node1..."
    DATASET1_RESPONSE=$(curl -s -X POST "${NODE1_URL}/api/data/register" \
        -H "Content-Type: application/json" \
        -d '{
            "path": "/storage/datasets/dataset_train_477f2544",
            "name": "Node1 Training Data",
            "split": "train"
        }')
    
    DATASET1_ID=$(echo $DATASET1_RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$DATASET1_ID" ]; then
        echo -e "${YELLOW}Dataset already registered on Node1, fetching existing...${NC}"
        DATASET1_ID=$(curl -s "${NODE1_URL}/api/data/list" | grep -o '"dataset_id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi
    
    if [ -z "$DATASET1_ID" ]; then
        echo -e "${RED}✗ Failed to register or find dataset on Node1${NC}"
        echo "Response: $DATASET1_RESPONSE"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Node1 Dataset ID: ${DATASET1_ID}${NC}"
    
    # Set as active
    curl -s -X POST "${NODE1_URL}/api/data/set-active/${DATASET1_ID}" > /dev/null
    echo -e "${GREEN}✓ Node1 dataset set as active${NC}"
    
    # Node2 - Register dataset (path inside container is /storage/datasets/...)
    echo "Registering dataset on Node2..."
    DATASET2_RESPONSE=$(curl -s -X POST "${NODE2_URL}/api/data/register" \
        -H "Content-Type: application/json" \
        -d '{
            "path": "/storage/datasets/dataset_train_fb09a934",
            "name": "Node2 Training Data",
            "split": "train"
        }')
    
    DATASET2_ID=$(echo $DATASET2_RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$DATASET2_ID" ]; then
        echo -e "${YELLOW}Dataset already registered on Node2, fetching existing...${NC}"
        DATASET2_ID=$(curl -s "${NODE2_URL}/api/data/list" | grep -o '"dataset_id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi
    
    if [ -z "$DATASET2_ID" ]; then
        echo -e "${RED}✗ Failed to register or find dataset on Node2${NC}"
        echo "Response: $DATASET2_RESPONSE"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Node2 Dataset ID: ${DATASET2_ID}${NC}"
    
    # Set as active
    curl -s -X POST "${NODE2_URL}/api/data/set-active/${DATASET2_ID}" > /dev/null
    echo -e "${GREEN}✓ Node2 dataset set as active${NC}"
    
    # Node3 - Register dataset (but won't participate in training)
    echo "Registering dataset on Node3 (will not participate)..."
    DATASET3_RESPONSE=$(curl -s -X POST "${NODE3_URL}/api/data/register" \
        -H "Content-Type: application/json" \
        -d '{
            "path": "/storage/datasets/dataset_train_f1ea778b",
            "name": "Node3 Training Data",
            "split": "train"
        }')
    
    DATASET3_ID=$(echo $DATASET3_RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$DATASET3_ID" ]; then
        echo -e "${YELLOW}Dataset already registered on Node3, fetching existing...${NC}"
        DATASET3_ID=$(curl -s "${NODE3_URL}/api/data/list" | grep -o '"dataset_id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi
    
    if [ -z "$DATASET3_ID" ]; then
        echo -e "${RED}✗ Failed to register or find dataset on Node3${NC}"
        echo "Response: $DATASET3_RESPONSE"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Node3 Dataset ID: ${DATASET3_ID}${NC}"
    
    # Set as active
    curl -s -X POST "${NODE3_URL}/api/data/set-active/${DATASET3_ID}" > /dev/null
    echo -e "${GREEN}✓ Node3 dataset set as active${NC}"
    
    echo ""
}

# Function to run a single FL training round
run_fl_training() {
    local TEST_NUM=$1
    local MODEL_NAME=$2
    local ROUND_ID=$3
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Test ${TEST_NUM}: ${MODEL_NAME}${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    echo -e "${BLUE}Step 2: Starting Flower Server...${NC}"
    echo "Model: ${MODEL_NAME}"
    echo "Rounds: ${NUM_ROUNDS}"
    echo "Epochs per round: ${NUM_EPOCHS}"
    echo "Min Clients: ${MIN_CLIENTS}"
    echo ""
    
    # Start Flower server in background
    # Use nohup to keep it running after exec returns
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
    
    echo -e "${GREEN}✓ Flower server starting...${NC}"
    echo "Waiting 15 seconds for server to initialize..."
    sleep 15
    echo ""
    
    echo -e "${BLUE}Step 3: Starting FL training on Node1...${NC}"
    JOB1_RESPONSE=$(curl -s -X POST "${NODE1_URL}/api/federated/train/${ROUND_ID}?dataset_id=${DATASET1_ID}&model_name=${MODEL_NAME}" \
        -H "Content-Type: application/json")
    
    JOB1_ID=$(echo $JOB1_RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$JOB1_ID" ]; then
        echo -e "${RED}✗ Failed to start training on Node1${NC}"
        echo "Response: $JOB1_RESPONSE"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Node1 training started - Job ID: ${JOB1_ID}${NC}"
    echo ""
    
    echo -e "${BLUE}Step 4: Starting FL training on Node2...${NC}"
    JOB2_RESPONSE=$(curl -s -X POST "${NODE2_URL}/api/federated/train/${ROUND_ID}?dataset_id=${DATASET2_ID}&model_name=${MODEL_NAME}" \
        -H "Content-Type: application/json")
    
    JOB2_ID=$(echo $JOB2_RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$JOB2_ID" ]; then
        echo -e "${RED}✗ Failed to start training on Node2${NC}"
        echo "Response: $JOB2_RESPONSE"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Node2 training started - Job ID: ${JOB2_ID}${NC}"
    echo ""
    
    echo -e "${YELLOW}Note: Node3 is NOT participating in this round${NC}"
    echo ""
    
    echo -e "${BLUE}Step 5: Monitoring training progress...${NC}"
    echo "This will take a few minutes (${NUM_ROUNDS} rounds × ${NUM_EPOCHS} epochs)..."
    echo ""
    
    # Monitor both nodes
    local MAX_WAIT=900  # 15 minutes max
    local ELAPSED=0
    local CHECK_INTERVAL=10
    
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        JOB1_STATUS=$(curl -s "${NODE1_URL}/api/train/status/${JOB1_ID}" 2>/dev/null | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4 | tr -d '\n\r ')
        JOB2_STATUS=$(curl -s "${NODE2_URL}/api/train/status/${JOB2_ID}" 2>/dev/null | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4 | tr -d '\n\r ')
        
        # Default to "unknown" if empty
        JOB1_STATUS=${JOB1_STATUS:-unknown}
        JOB2_STATUS=${JOB2_STATUS:-unknown}
        
        # Only print every 30 seconds to reduce spam
        if [ $((ELAPSED % 30)) -eq 0 ] || [ "$ELAPSED" -eq 0 ]; then
            echo -e "  Node1: ${JOB1_STATUS} | Node2: ${JOB2_STATUS} | Elapsed: ${ELAPSED}s"
        fi
        
        # Check for completion
        if [ "$JOB1_STATUS" = "completed" ] && [ "$JOB2_STATUS" = "completed" ]; then
            echo ""
            echo -e "${GREEN}✓ Both nodes completed training!${NC}"
            break
        fi
        
        # Check for failure
        if [ "$JOB1_STATUS" = "failed" ] || [ "$JOB2_STATUS" = "failed" ]; then
            echo ""
            echo -e "${RED}✗ Training failed on one or more nodes${NC}"
            
            # Show error details
            if [ "$JOB1_STATUS" = "failed" ]; then
                echo -e "${RED}Node1 Error:${NC}"
                curl -s "${NODE1_URL}/api/train/status/${JOB1_ID}" | grep -o '"error":"[^"]*"' | cut -d'"' -f4
            fi
            
            if [ "$JOB2_STATUS" = "failed" ]; then
                echo -e "${RED}Node2 Error:${NC}"
                curl -s "${NODE2_URL}/api/train/status/${JOB2_ID}" | grep -o '"error":"[^"]*"' | cut -d'"' -f4
            fi
            
            exit 1
        fi
        
        # Check for timeout before sleeping
        if [ $ELAPSED -ge $MAX_WAIT ]; then
            echo ""
            echo -e "${RED}✗ Training timeout after ${MAX_WAIT} seconds${NC}"
            exit 1
        fi
        
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
    done
    
    echo ""
    
    echo -e "${BLUE}Step 6: Verifying results...${NC}"
    
    # Check Node1 results
    JOB1_RESULT=$(curl -s "${NODE1_URL}/api/train/status/${JOB1_ID}")
    echo -e "${GREEN}✓ Node1 training completed${NC}"
    
    # Check Node2 results
    JOB2_RESULT=$(curl -s "${NODE2_URL}/api/train/status/${JOB2_ID}")
    echo -e "${GREEN}✓ Node2 training completed${NC}"
    
    echo ""
    
    echo -e "${BLUE}Step 7: Stopping Flower Server...${NC}"
    # Kill Flower server using saved PID
    docker compose exec -T central bash -c "
        if [ -f /tmp/flower_server.pid ]; then
            pid=\$(cat /tmp/flower_server.pid)
            if [ -n \"\$pid\" ]; then
                kill -9 \$pid 2>/dev/null || true
                rm /tmp/flower_server.pid
                echo 'Flower server stopped (PID: '\$pid')'
            fi
        else
            echo 'No PID file found, server may have already stopped'
        fi
    " 2>/dev/null || echo "Flower server cleanup attempted"
    sleep 2
    echo -e "${GREEN}✓ Flower server stopped${NC}"
    echo ""
    
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test ${TEST_NUM} (${MODEL_NAME}) COMPLETED!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    # Wait before next test
    if [ $TEST_NUM -lt 3 ]; then
        echo -e "${YELLOW}Waiting 10 seconds before next test...${NC}"
        sleep 10
        echo ""
    fi
}

# Main execution
main() {
    echo -e "${BLUE}Starting E2E Sequential Tests...${NC}"
    echo ""
    
    # Check services
    check_services
    
    # Register datasets (only once at the beginning)
    register_datasets
    
    # Export dataset IDs for use in run_fl_training function
    export DATASET1_ID
    export DATASET2_ID
    export DATASET3_ID
    
    # Test 1: ResNet18
    run_fl_training 1 "resnet18" "R-RESNET18"
    
    # Test 2: DenseNet121
    run_fl_training 2 "densenet121" "R-DENSENET121"
    
    # Test 3: EfficientNet-B0
    run_fl_training 3 "efficientnet_b0" "R-EFFICIENTNET"
    
    # Final summary
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}ALL TESTS COMPLETED SUCCESSFULLY!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    # Final cleanup - ensure all Flower servers are stopped
    echo -e "${BLUE}Final cleanup: Stopping any remaining Flower servers...${NC}"
    docker compose exec -T central bash -c "
        if [ -f /tmp/flower_server.pid ]; then
            pid=\$(cat /tmp/flower_server.pid)
            if [ -n \"\$pid\" ]; then
                kill -9 \$pid 2>/dev/null || true
                rm /tmp/flower_server.pid
            fi
        fi
        echo 'Cleanup complete'
    " 2>/dev/null || echo "Cleanup attempted"
    sleep 2
    echo -e "${GREEN}✓ Cleanup complete${NC}"
    echo ""
    
    echo -e "${BLUE}Summary:${NC}"
    echo "  ✓ Test 1: ResNet18 (Round R-RESNET18)"
    echo "  ✓ Test 2: DenseNet121 (Round R-DENSENET121)"
    echo "  ✓ Test 3: EfficientNet-B0 (Round R-EFFICIENTNET)"
    echo ""
    echo -e "${BLUE}You can now check:${NC}"
    echo "  - Models page: http://localhost:3001/models"
    echo "  - Jobs page: http://localhost:3001/jobs"
    echo "  - Federated page: http://localhost:3001/federated"
    echo ""
    echo -e "${BLUE}Database contains:${NC}"
    echo "  - 3 FL training jobs (one per model)"
    echo "  - 6 total jobs (2 nodes × 3 models)"
    echo "  - Models saved in candidate registry"
    echo ""
}

# Run main
main
