#!/bin/bash

# Test Differential Privacy Implementation
# Tests 3 scenarios: No DP (baseline), DP relaxed (ε=10), DP strong (ε=1)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "============================================================"
echo "🔒 DIFFERENTIAL PRIVACY TESTING"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to wait for services
wait_for_services() {
    echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"
    sleep 10
    
    for i in {1..30}; do
        if curl -s http://localhost:8001/api/health > /dev/null 2>&1 && \
           curl -s http://localhost:8002/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Services are ready${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
    done
    
    echo -e "${RED}✗ Services failed to start${NC}"
    return 1
}

# Function to check if Opacus is installed
check_opacus() {
    echo -e "${BLUE}🔍 Checking Opacus installation...${NC}"
    
    if docker compose exec -T node1-worker python -c "import opacus; print(f'Opacus version: {opacus.__version__}')" 2>/dev/null; then
        echo -e "${GREEN}✓ Opacus is installed${NC}"
        return 0
    else
        echo -e "${RED}✗ Opacus is NOT installed${NC}"
        echo -e "${YELLOW}  Installing Opacus...${NC}"
        docker compose exec -T node1-worker pip install opacus>=1.4.0 dp-accounting>=0.4.0
        return $?
    fi
}

# Function to update DP config in docker-compose.yml
update_dp_config() {
    local enable_dp=$1
    local epsilon=$2
    local noise_multiplier=$3
    
    echo -e "${BLUE}📝 Updating DP configuration...${NC}"
    echo "  ENABLE_DP: $enable_dp"
    echo "  DP_TARGET_EPSILON: $epsilon"
    echo "  DP_NOISE_MULTIPLIER: $noise_multiplier"
    
    # Backup original
    cp docker-compose.yml docker-compose.yml.backup
    
    # Update config for all workers
    sed -i "s/ENABLE_DP: \".*\"/ENABLE_DP: \"$enable_dp\"/" docker-compose.yml
    sed -i "s/DP_TARGET_EPSILON: \".*\"/DP_TARGET_EPSILON: \"$epsilon\"/" docker-compose.yml
    sed -i "s/DP_NOISE_MULTIPLIER: \".*\"/DP_NOISE_MULTIPLIER: \"$noise_multiplier\"/" docker-compose.yml
    
    echo -e "${GREEN}✓ Configuration updated${NC}"
}

# Function to restart workers
restart_workers() {
    echo -e "${BLUE}🔄 Restarting workers...${NC}"
    docker compose restart node1-worker node2-worker
    sleep 5
    echo -e "${GREEN}✓ Workers restarted${NC}"
}

# Function to run FL training
run_fl_training() {
    local test_name=$1
    local round_id=$2
    
    echo ""
    echo "============================================================"
    echo "🚀 Running FL Training: $test_name"
    echo "============================================================"
    
    # Start Flower Server
    echo -e "${BLUE}📡 Starting Flower Server...${NC}"
    docker compose exec -d central python -m app.flower_server \
        --num_rounds 1 \
        --min_clients 2 \
        --model_name resnet18 \
        --num_epochs 2 \
        --learning_rate 0.001
    
    sleep 5
    
    # Get active datasets
    echo -e "${BLUE}🔍 Getting active datasets...${NC}"
    DATASET1=$(curl -s http://localhost:8001/api/data/list | jq -r '.datasets[] | select(.is_active==true) | .dataset_id' | head -1)
    DATASET2=$(curl -s http://localhost:8002/api/data/list | jq -r '.datasets[] | select(.is_active==true) | .dataset_id' | head -1)
    
    if [ -z "$DATASET1" ] || [ -z "$DATASET2" ]; then
        echo -e "${RED}✗ No active datasets found${NC}"
        return 1
    fi
    
    echo "  Node1 dataset: $DATASET1"
    echo "  Node2 dataset: $DATASET2"
    
    # Start training on Node1
    echo -e "${BLUE}🏥 Starting training on Node1...${NC}"
    JOB1=$(curl -s -X POST "http://localhost:8001/api/federated/train/$round_id?dataset_id=$DATASET1&model_name=resnet18&num_epochs=2&learning_rate=0.001" | jq -r '.job_id')
    echo "  Job ID: $JOB1"
    
    # Start training on Node2
    echo -e "${BLUE}🏥 Starting training on Node2...${NC}"
    JOB2=$(curl -s -X POST "http://localhost:8002/api/federated/train/$round_id?dataset_id=$DATASET2&model_name=resnet18&num_epochs=2&learning_rate=0.001" | jq -r '.job_id')
    echo "  Job ID: $JOB2"
    
    # Monitor progress
    echo -e "${BLUE}⏳ Monitoring training progress...${NC}"
    
    for i in {1..60}; do
        STATUS1=$(curl -s "http://localhost:8001/api/jobs/$JOB1/status" | jq -r '.status')
        STATUS2=$(curl -s "http://localhost:8002/api/jobs/$JOB2/status" | jq -r '.status')
        
        echo "  [$i/60] Node1: $STATUS1 | Node2: $STATUS2"
        
        if [ "$STATUS1" = "completed" ] && [ "$STATUS2" = "completed" ]; then
            echo -e "${GREEN}✓ Training completed on both nodes${NC}"
            break
        fi
        
        if [ "$STATUS1" = "failed" ] || [ "$STATUS2" = "failed" ]; then
            echo -e "${RED}✗ Training failed${NC}"
            return 1
        fi
        
        sleep 10
    done
    
    # Get results
    echo ""
    echo "📊 Results:"
    echo "----------------------------------------"
    
    RESULT1=$(curl -s "http://localhost:8001/api/jobs/$JOB1/status")
    RESULT2=$(curl -s "http://localhost:8002/api/jobs/$JOB2/status")
    
    ACC1=$(echo "$RESULT1" | jq -r '.result.accuracy // "N/A"')
    ACC2=$(echo "$RESULT2" | jq -r '.result.accuracy // "N/A"')
    
    EPSILON1=$(echo "$RESULT1" | jq -r '.result.dp_epsilon // "N/A"')
    EPSILON2=$(echo "$RESULT2" | jq -r '.result.dp_epsilon // "N/A"')
    
    echo "Node1:"
    echo "  Accuracy: $ACC1"
    echo "  ε (epsilon): $EPSILON1"
    echo ""
    echo "Node2:"
    echo "  Accuracy: $ACC2"
    echo "  ε (epsilon): $EPSILON2"
    echo "----------------------------------------"
    
    # Save results to file
    echo "$test_name,$ACC1,$ACC2,$EPSILON1,$EPSILON2" >> dp_test_results.csv
    
    # Check logs for DP messages
    echo ""
    echo "🔍 Checking logs for DP indicators..."
    if docker compose logs node1-worker 2>/dev/null | grep -q "DP-SGD enabled"; then
        echo -e "${GREEN}✓ DP-SGD was enabled${NC}"
    else
        echo -e "${YELLOW}⚠ DP-SGD was NOT enabled${NC}"
    fi
    
    # Stop Flower Server
    docker compose stop central
    sleep 2
}

# Main test sequence
main() {
    cd "$PROJECT_ROOT"
    
    echo "Project root: $PROJECT_ROOT"
    echo ""
    
    # Check if services are running
    if ! docker compose ps | grep -q "Up"; then
        echo -e "${YELLOW}⚠ Services not running. Starting...${NC}"
        docker compose up -d
        wait_for_services
    else
        echo -e "${GREEN}✓ Services already running${NC}"
    fi
    
    # Check Opacus installation
    check_opacus || exit 1
    
    # Initialize results file
    echo "Test,Node1_Accuracy,Node2_Accuracy,Node1_Epsilon,Node2_Epsilon" > dp_test_results.csv
    
    echo ""
    echo "============================================================"
    echo "📋 TEST PLAN"
    echo "============================================================"
    echo "1. Baseline (No DP) - Expected: ~85-95% accuracy"
    echo "2. DP Relaxed (ε=10) - Expected: ~80-90% accuracy"
    echo "3. DP Strong (ε=1) - Expected: ~70-85% accuracy"
    echo "============================================================"
    echo ""
    
    read -p "Press Enter to start tests (or Ctrl+C to cancel)..."
    
    # TEST 1: Baseline (No DP)
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "TEST 1: BASELINE (NO DP)"
    echo "════════════════════════════════════════════════════════════"
    update_dp_config "false" "1.0" "1.0"
    restart_workers
    run_fl_training "Baseline_NoDP" "R-DP-TEST-1"
    
    # TEST 2: DP Relaxed (ε=10)
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "TEST 2: DP RELAXED (ε=10)"
    echo "════════════════════════════════════════════════════════════"
    update_dp_config "true" "10.0" "0.5"
    restart_workers
    run_fl_training "DP_Relaxed_Epsilon10" "R-DP-TEST-2"
    
    # TEST 3: DP Strong (ε=1)
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "TEST 3: DP STRONG (ε=1)"
    echo "════════════════════════════════════════════════════════════"
    update_dp_config "true" "1.0" "1.0"
    restart_workers
    run_fl_training "DP_Strong_Epsilon1" "R-DP-TEST-3"
    
    # Restore original config
    echo ""
    echo -e "${BLUE}🔄 Restoring original configuration...${NC}"
    mv docker-compose.yml.backup docker-compose.yml
    restart_workers
    
    # Summary
    echo ""
    echo "============================================================"
    echo "📊 TEST SUMMARY"
    echo "============================================================"
    echo ""
    cat dp_test_results.csv | column -t -s,
    echo ""
    echo "Results saved to: dp_test_results.csv"
    echo ""
    echo -e "${GREEN}✅ All tests completed!${NC}"
    echo "============================================================"
}

# Run main
main
