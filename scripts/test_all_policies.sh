#!/bin/bash

# Complete policy testing script
# Tests LOG, WARN, and REJECT policies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "========================================================================"
echo -e "${BLUE}🔐 SECURITY POLICY TESTING SUITE${NC}"
echo "========================================================================"
echo ""

# Function to test a policy
test_policy() {
    local policy=$1
    local min_valid=$2
    
    echo ""
    echo "========================================================================"
    echo -e "${CYAN}TESTING POLICY: ${policy}${NC}"
    echo "========================================================================"
    echo "Min Valid Signatures: ${min_valid}"
    echo ""
    
    # Start Flower server in background with policy
    echo -e "${YELLOW}🌸 Starting Flower server with ${policy} policy...${NC}"
    
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
        SIGNATURE_POLICY='${policy}' \
        MIN_VALID_SIGNATURES='${min_valid}' \
        python -m app.flower_server > /tmp/flower_${policy}.log 2>&1
    "
    
    sleep 10
    echo -e "${GREEN}✓ Flower server started${NC}"
    
    # Trigger FL training on both nodes
    echo -e "${YELLOW}👷 Starting FL training on nodes...${NC}"
    
    # Get tokens
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
    
    ROUND_ID="R-POLICY-TEST-${policy}-$(date +%s)"
    
    # Start training
    curl -s -X POST "http://localhost:8001/api/federated/train/${ROUND_ID}?dataset_id=${DATASET1}&model_name=resnet18" \
        -H "Authorization: Bearer ${TOKEN1}" > /dev/null
    
    curl -s -X POST "http://localhost:8002/api/federated/train/${ROUND_ID}?dataset_id=${DATASET2}&model_name=resnet18" \
        -H "Authorization: Bearer ${TOKEN2}" > /dev/null
    
    echo -e "${GREEN}✓ Training jobs submitted${NC}"
    
    # Wait for completion (max 3 minutes)
    echo -e "${YELLOW}⏳ Waiting for training to complete...${NC}"
    
    local max_wait=180
    local elapsed=0
    local completed=false
    
    while [ $elapsed -lt $max_wait ]; do
        # Check if Flower server finished
        if docker compose exec central test -f /tmp/flower_${policy}.log 2>/dev/null; then
            if docker compose exec central grep -q "FL training complete\|ROUND.*COMPLETE" /tmp/flower_${policy}.log 2>/dev/null; then
                completed=true
                break
            fi
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
        
        if [ $((elapsed % 30)) -eq 0 ]; then
            echo "  ... still running (${elapsed}s elapsed)"
        fi
    done
    
    if [ "$completed" = true ]; then
        echo -e "${GREEN}✓ Training completed${NC}"
    else
        echo -e "${YELLOW}⚠ Training timeout (may still be running)${NC}"
    fi
    
    # Display results
    echo ""
    echo "========================================================================"
    echo -e "${CYAN}📊 RESULTS FOR POLICY: ${policy}${NC}"
    echo "========================================================================"
    echo ""
    
    # Show signature verification stats
    echo -e "${BLUE}🔐 Signature Verification:${NC}"
    docker compose exec central cat /tmp/flower_${policy}.log 2>/dev/null | \
        grep -A 10 "Signature Verification Stats\|Signature:" | head -20 || \
        echo "  No signature stats found"
    
    echo ""
    echo -e "${BLUE}📋 Policy Actions:${NC}"
    docker compose exec central cat /tmp/flower_${policy}.log 2>/dev/null | \
        grep "Policy:\|REJECT\|WARN" || \
        echo "  No policy actions logged"
    
    echo ""
    echo -e "${BLUE}📈 Aggregation Summary:${NC}"
    docker compose exec central cat /tmp/flower_${policy}.log 2>/dev/null | \
        grep -E "ROUND.*COMPLETE|aggregate_fit|received.*results" | tail -5 || \
        echo "  No aggregation info found"
    
    echo ""
    echo -e "${GREEN}✓ Test for ${policy} policy completed${NC}"
    echo ""
    
    # Small delay before next test
    sleep 5
}

# Check if services are running
echo "🔍 Checking services..."
if ! docker compose ps | grep -q "node1-api.*Up"; then
    echo -e "${RED}❌ Services not running${NC}"
    echo "Please start services first: docker compose up -d"
    exit 1
fi
echo -e "${GREEN}✓ Services are running${NC}"
echo ""

# Test each policy
echo "This will test 3 security policies:"
echo "  1. LOG - Logs invalid signatures but continues"
echo "  2. WARN - Warns if too many invalid signatures"
echo "  3. REJECT - Excludes clients with invalid signatures"
echo ""
echo "Press Enter to start or Ctrl+C to cancel..."
read

# Test 1: LOG policy
test_policy "log" "0.8"

# Test 2: WARN policy
test_policy "warn" "0.8"

# Test 3: REJECT policy (with 100% threshold for strict mode)
test_policy "reject" "1.0"

# Final summary
echo ""
echo "========================================================================"
echo -e "${GREEN}🎉 ALL POLICY TESTS COMPLETED${NC}"
echo "========================================================================"
echo ""
echo "Summary:"
echo "  ✓ LOG policy - Most permissive, logs but continues"
echo "  ✓ WARN policy - Balanced, warns if threshold not met"
echo "  ✓ REJECT policy - Strictest, excludes invalid signatures"
echo ""
echo "Log files saved in central container:"
echo "  - /tmp/flower_log.log"
echo "  - /tmp/flower_warn.log"
echo "  - /tmp/flower_reject.log"
echo ""
echo "To view a specific log:"
echo "  docker compose exec central cat /tmp/flower_<policy>.log"
echo ""
