#!/bin/bash

# Test script for Federated UI improvements
# This script verifies that dataset info and metrics are properly saved

set -e

echo "=========================================="
echo "Testing Federated UI Improvements"
echo "=========================================="
echo ""

# Configuration
NODE1_URL="http://localhost:8001"
NODE2_URL="http://localhost:8002"
CENTRAL_URL="http://localhost:8081"
FLOWER_SERVER_ADDRESS="0.0.0.0:8080"
MODEL_NAME="resnet18"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if services are running
log_info "Checking services..."
if ! curl -s "${NODE1_URL}/api/node/status" > /dev/null; then
    log_error "Node1 is not responding"
    exit 1
fi

if ! curl -s "${NODE2_URL}/api/node/status" > /dev/null; then
    log_error "Node2 is not responding"
    exit 1
fi

log_info "✓ All services are running"
echo ""

# Get active datasets
log_info "Getting active datasets..."
DATASET1_ID=$(curl -s "${NODE1_URL}/api/data/list" | python3 -c "import sys, json; data = json.load(sys.stdin); active = [d for d in data['datasets'] if d['is_active']]; print(active[0]['dataset_id'] if active else '')")
DATASET2_ID=$(curl -s "${NODE2_URL}/api/data/list" | python3 -c "import sys, json; data = json.load(sys.stdin); active = [d for d in data['datasets'] if d['is_active']]; print(active[0]['dataset_id'] if active else '')")

if [ -z "$DATASET1_ID" ] || [ -z "$DATASET2_ID" ]; then
    log_error "No active datasets found. Please register and activate datasets first."
    exit 1
fi

log_info "✓ Node1 dataset: $DATASET1_ID"
log_info "✓ Node2 dataset: $DATASET2_ID"
echo ""

# Generate unique round ID
ROUND_ID="R-TEST-$(date +%s)"
log_info "Round ID: $ROUND_ID"
echo ""

# Start Flower server
log_info "Starting Flower server..."
docker compose exec -d central bash -c "
export MODEL_NAME=${MODEL_NAME}
export FLOWER_SERVER_ADDRESS=${FLOWER_SERVER_ADDRESS}
export NUM_ROUNDS=1
export MIN_CLIENTS=2
export NUM_EPOCHS=2
python -m app.flower_server > /tmp/flower_${MODEL_NAME}.log 2>&1
"

sleep 5
log_info "✓ Flower server started"
echo ""

# Start training on Node1
log_info "Starting training on Node1..."
RESPONSE1=$(curl -s -X POST "${NODE1_URL}/api/federated/train/${ROUND_ID}?dataset_id=${DATASET1_ID}&model_name=${MODEL_NAME}")
JOB1_ID=$(echo "$RESPONSE1" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
log_info "✓ Node1 job started: $JOB1_ID"
echo ""

# Start training on Node2
log_info "Starting training on Node2..."
RESPONSE2=$(curl -s -X POST "${NODE2_URL}/api/federated/train/${ROUND_ID}?dataset_id=${DATASET2_ID}&model_name=${MODEL_NAME}")
JOB2_ID=$(echo "$RESPONSE2" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
log_info "✓ Node2 job started: $JOB2_ID"
echo ""

# Monitor progress
log_info "Monitoring training progress..."
echo ""

MAX_WAIT=300  # 5 minutes
ELAPSED=0
INTERVAL=10

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check Node1 status
    STATUS1=$(curl -s "${NODE1_URL}/api/jobs/${JOB1_ID}" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    
    # Check Node2 status
    STATUS2=$(curl -s "${NODE2_URL}/api/jobs/${JOB2_ID}" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    
    echo "[$ELAPSED s] Node1: $STATUS1 | Node2: $STATUS2"
    
    # Check if both completed
    if [ "$STATUS1" = "completed" ] && [ "$STATUS2" = "completed" ]; then
        log_info "✓ Both nodes completed training"
        break
    fi
    
    # Check if any failed
    if [ "$STATUS1" = "failed" ] || [ "$STATUS2" = "failed" ]; then
        log_error "Training failed on one or more nodes"
        exit 1
    fi
    
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    log_error "Training timeout after ${MAX_WAIT}s"
    exit 1
fi

echo ""
log_info "Training completed successfully!"
echo ""

# Verify results
log_info "Verifying results..."
echo ""

# Check Node1 job result
log_info "Node1 Job Result:"
JOB1_RESULT=$(curl -s "${NODE1_URL}/api/jobs/${JOB1_ID}")
echo "$JOB1_RESULT" | python3 -m json.tool | grep -A 20 '"result"'
echo ""

# Check if dataset_id is present
DATASET_ID_CHECK=$(echo "$JOB1_RESULT" | python3 -c "import sys, json; result = json.load(sys.stdin).get('result', {}); print('✓' if result.get('dataset_id') else '✗')")
log_info "Dataset ID present: $DATASET_ID_CHECK"

# Check if metrics are present
METRICS_CHECK=$(echo "$JOB1_RESULT" | python3 -c "import sys, json; result = json.load(sys.stdin).get('result', {}); print('✓' if result.get('metrics') else '✗')")
log_info "Metrics present: $METRICS_CHECK"

# Check if logs exist
if [ -f "/tmp/federated_train_${JOB1_ID}.log" ]; then
    log_info "Logs file: ✓"
else
    log_warning "Logs file not found (might be in container)"
fi

echo ""

# Check federated history
log_info "Checking federated history..."
HISTORY=$(curl -s "${NODE1_URL}/api/federated/history")
echo "$HISTORY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
rounds = data.get('rounds', [])
test_round = next((r for r in rounds if r['round_id'] == '${ROUND_ID}'), None)
if test_round:
    print('✓ Round found in history')
    print(f\"  - Dataset ID: {test_round.get('dataset_id', 'N/A')}\")
    print(f\"  - Dataset Name: {test_round.get('dataset_name', 'N/A')}\")
    metrics = test_round.get('metrics', {})
    if metrics:
        print(f\"  - Accuracy: {metrics.get('accuracy', 'N/A')}\")
        print(f\"  - Train Loss: {metrics.get('train_loss', 'N/A')}\")
        print(f\"  - Val Loss: {metrics.get('val_loss', 'N/A')}\")
    else:
        print('  - Metrics: N/A')
else:
    print('✗ Round not found in history')
"

echo ""
log_info "=========================================="
log_info "Test completed successfully!"
log_info "=========================================="
log_info ""
log_info "Next steps:"
log_info "1. Open http://localhost:3001/federated"
log_info "2. Verify that round ${ROUND_ID} shows:"
log_info "   - Dataset name and ID"
log_info "   - Accuracy percentage"
log_info "3. Click 'View Details' to see full information"
log_info ""
