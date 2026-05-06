#!/bin/bash

# Simple DP Test Script - Tests DP implementation without complex dependencies

set -e

echo "============================================================"
echo "🔒 DIFFERENTIAL PRIVACY - SIMPLE TEST"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Check Opacus installation
echo -e "${BLUE}Step 1: Checking Opacus installation...${NC}"
if docker compose exec -T node1-worker python -c "import opacus; print('Opacus version:', opacus.__version__)" 2>&1; then
    echo -e "${GREEN}✓ Opacus is installed${NC}"
else
    echo -e "${YELLOW}⚠ Opacus not found. Installing...${NC}"
    docker compose exec -T node1-worker pip install opacus>=1.4.0 dp-accounting>=0.4.0
fi

echo ""

# Step 2: Check current DP configuration
echo -e "${BLUE}Step 2: Current DP configuration in docker-compose.yml:${NC}"
grep -A 5 "ENABLE_DP:" docker-compose.yml | head -6
echo ""

# Step 3: Test DP code is present in flower_client.py
echo -e "${BLUE}Step 3: Checking DP implementation in flower_client.py...${NC}"
if grep -q "enable_dp" services/node/worker/app/flower_client.py; then
    echo -e "${GREEN}✓ DP code found in flower_client.py${NC}"
    echo "  Key DP parameters found:"
    grep "self.enable_dp" services/node/worker/app/flower_client.py | head -3
else
    echo -e "${RED}✗ DP code NOT found${NC}"
fi

echo ""

# Step 4: Check DP in flower_strategy.py
echo -e "${BLUE}Step 4: Checking DP implementation in flower_strategy.py...${NC}"
if grep -q "enable_server_dp" shared/python/node_core/node_core/flower_strategy.py; then
    echo -e "${GREEN}✓ Server-side DP code found${NC}"
else
    echo -e "${YELLOW}⚠ Server-side DP code NOT found${NC}"
fi

echo ""

# Step 5: Manual test instructions
echo "============================================================"
echo "📋 MANUAL TEST INSTRUCTIONS"
echo "============================================================"
echo ""
echo "To test DP, follow these steps:"
echo ""
echo "1. Enable DP in docker-compose.yml:"
echo "   Change: ENABLE_DP: \"false\" → ENABLE_DP: \"true\""
echo ""
echo "2. Restart workers:"
echo "   docker compose restart node1-worker node2-worker"
echo ""
echo "3. Run FL training:"
echo "   ./scripts/test_single_fl.sh"
echo ""
echo "4. Check logs for DP indicators:"
echo "   docker compose logs node1-worker | grep -i \"dp\""
echo "   docker compose logs node1-worker | grep -i \"epsilon\""
echo ""
echo "5. Look for these messages:"
echo "   - '🔒 Initializing Differential Privacy...'"
echo "   - 'DP-SGD enabled'"
echo "   - 'ε: X.XX' (epsilon values)"
echo "   - 'Final privacy spent: ε = X.XX'"
echo ""
echo "============================================================"
echo ""

# Step 6: Quick automated test
echo -e "${BLUE}Step 6: Would you like to run a quick automated test? (y/n)${NC}"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Running quick DP test..."
    echo ""
    
    # Backup config
    cp docker-compose.yml docker-compose.yml.backup
    
    # Enable DP
    echo "Enabling DP..."
    sed -i 's/ENABLE_DP: "false"/ENABLE_DP: "true"/' docker-compose.yml
    sed -i 's/DP_TARGET_EPSILON: "1.0"/DP_TARGET_EPSILON: "10.0"/' docker-compose.yml
    sed -i 's/DP_NOISE_MULTIPLIER: "1.0"/DP_NOISE_MULTIPLIER: "0.5"/' docker-compose.yml
    
    echo "Restarting workers..."
    docker compose restart node1-worker node2-worker
    sleep 5
    
    echo ""
    echo "Starting Flower Server..."
    docker compose exec -d central python -m app.flower_server \
        --num_rounds 1 \
        --min_clients 2 \
        --model_name resnet18 \
        --num_epochs 2 \
        --learning_rate 0.001
    
    sleep 5
    
    echo ""
    echo "⏳ Training will start automatically when clients connect..."
    echo "   Monitor logs with: docker compose logs -f node1-worker"
    echo ""
    echo "   Press Ctrl+C when done, then run:"
    echo "   mv docker-compose.yml.backup docker-compose.yml"
    echo "   docker compose restart node1-worker node2-worker"
    echo ""
    
    # Show logs
    docker compose logs -f node1-worker
else
    echo "Test skipped. Follow manual instructions above."
fi

echo ""
echo -e "${GREEN}✅ DP check complete!${NC}"
