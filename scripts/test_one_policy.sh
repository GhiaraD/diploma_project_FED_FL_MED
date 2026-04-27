#!/bin/bash

# Test a single policy

set -e

POLICY=${1:-log}
MIN_VALID=${2:-0.8}

echo "========================================================================"
echo "🔐 TESTING POLICY: $POLICY"
echo "========================================================================"
echo "Min Valid Signatures: $MIN_VALID"
echo ""

# Start Flower server
echo "🌸 Starting Flower server..."
docker compose exec -d central bash -c "
    cd /app &&
    MODEL_NAME='resnet18' \
    NUM_ROUNDS=1 \
    MIN_CLIENTS=2 \
    MIN_FIT_CLIENTS=2 \
    MIN_AVAILABLE_CLIENTS=2 \
    NUM_EPOCHS=2 \
    LEARNING_RATE=0.001 \
    OPTIMIZER='adam' \
    FLOWER_SERVER_ADDRESS='0.0.0.0:8080' \
    ENABLE_SSL='true' \
    CERTIFICATES_PATH='/certificates' \
    SIGNATURE_POLICY='$POLICY' \
    MIN_VALID_SIGNATURES='$MIN_VALID' \
    python -m app.flower_server > /tmp/flower_test.log 2>&1
"

sleep 10
echo "✓ Flower server started"
echo ""

# Get tokens
echo "🔑 Authenticating..."
TOKEN1=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin@node1.fed-med-fl.com&password=AdminNode1@2026" | \
    grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

TOKEN2=$(curl -s -X POST "http://localhost:8002/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin@node2.fed-med-fl.com&password=AdminNode2@2026" | \
    grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# Get datasets
DATASET1=$(curl -s -H "Authorization: Bearer ${TOKEN1}" "http://localhost:8001/api/data/active" | \
    python3 -c "import sys, json; data = json.load(sys.stdin); active = data.get('active_dataset'); print(active['dataset_id'] if active else '')")

DATASET2=$(curl -s -H "Authorization: Bearer ${TOKEN2}" "http://localhost:8002/api/data/active" | \
    python3 -c "import sys, json; data = json.load(sys.stdin); active = data.get('active_dataset'); print(active['dataset_id'] if active else '')")

ROUND_ID="R-TEST-$POLICY-$(date +%s)"

echo "✓ Authenticated"
echo ""

# Start training
echo "👷 Starting FL training..."
curl -s -X POST "http://localhost:8001/api/federated/train/${ROUND_ID}?dataset_id=${DATASET1}&model_name=resnet18" \
    -H "Authorization: Bearer ${TOKEN1}" > /dev/null

curl -s -X POST "http://localhost:8002/api/federated/train/${ROUND_ID}?dataset_id=${DATASET2}&model_name=resnet18" \
    -H "Authorization: Bearer ${TOKEN2}" > /dev/null

echo "✓ Training jobs submitted"
echo ""

# Monitor
echo "⏳ Monitoring (max 3 minutes)..."
MAX_WAIT=180
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if docker compose exec central grep -q "ROUND.*COMPLETE\|FL training complete" /tmp/flower_test.log 2>/dev/null; then
        echo "✓ Training completed!"
        break
    fi
    
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    
    if [ $((ELAPSED % 30)) -eq 0 ]; then
        echo "  ... ${ELAPSED}s elapsed"
    fi
done

echo ""
echo "========================================================================"
echo "📊 RESULTS"
echo "========================================================================"
echo ""

# Show full log
docker compose exec central cat /tmp/flower_test.log 2>&1

echo ""
echo "========================================================================"
echo "✓ Test completed"
echo "========================================================================"
