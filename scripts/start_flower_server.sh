#!/bin/bash
# Script pentru pornirea manuală a Flower Server
# Folosește acest script DUPĂ ce nodurile sunt gata să se conecteze

set -e

echo "🌸 Starting Flower Server..."
echo "=================================================="
echo ""
echo "Configuration:"
echo "  - Model: efficientnet_b0"
echo "  - Rounds: 2"
echo "  - Epochs per round: 2"
echo "  - Min clients: 2"
echo "  - SSL/mTLS: Enabled"
echo ""
echo "=================================================="
echo ""

# Start Flower Server in central container
docker compose exec central python -m app.flower_server \
  --num-rounds 2 \
  --model-name efficientnet_b0 \
  --num-epochs 2 \
  --min-available-clients 2 \
  --min-fit-clients 2

echo ""
echo "✅ Flower Server finished!"
