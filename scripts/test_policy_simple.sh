#!/bin/bash

# Simple policy test - runs Flower server in foreground to see all logs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

POLICY=${1:-log}

echo "========================================================================"
echo "🔐 TESTING SECURITY POLICY: $POLICY"
echo "========================================================================"
echo ""

# Check if services are running
if ! docker compose ps | grep -q "node1-api.*Up"; then
    echo "❌ Services not running. Please start with: docker compose up -d"
    exit 1
fi

echo "✓ Services are running"
echo ""

# Start Flower server in foreground
echo "🌸 Starting Flower server with policy: $POLICY"
echo "   (Watch for signature verification logs below)"
echo ""
echo "========================================================================"
echo ""

docker compose exec central bash -c "
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
MIN_VALID_SIGNATURES='0.8' \
python -m app.flower_server
"

echo ""
echo "========================================================================"
echo "✓ Flower server finished"
echo "========================================================================"
