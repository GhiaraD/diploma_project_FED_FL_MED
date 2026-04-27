#!/bin/bash

# Test Security Policies for Fed-Med-FL
# Tests: log, warn, reject policies with valid and invalid signatures

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================================================"
echo "🔐 SECURITY POLICY TESTING"
echo "========================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to cleanup
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    docker-compose down -v > /dev/null 2>&1 || true
    sleep 2
}

# Function to wait for service
wait_for_service() {
    local service=$1
    local url=$2
    local max_attempts=30
    local attempt=0
    
    echo "⏳ Waiting for $service..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo "✓ $service is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo "✗ $service failed to start"
    return 1
}

# Function to run test with specific policy
run_policy_test() {
    local policy=$1
    local min_valid=$2
    local test_name=$3
    
    echo ""
    echo "========================================================================"
    echo -e "${BLUE}TEST: $test_name${NC}"
    echo "========================================================================"
    echo "Policy: $policy"
    echo "Min Valid Signatures: $min_valid"
    echo ""
    
    # Update docker-compose.yml with policy
    echo "📝 Configuring policy..."
    
    # Backup original
    cp docker-compose.yml docker-compose.yml.backup
    
    # Update policy in docker-compose.yml
    sed -i "s/SIGNATURE_POLICY: \".*\"/SIGNATURE_POLICY: \"$policy\"/" docker-compose.yml
    sed -i "s/MIN_VALID_SIGNATURES: \".*\"/MIN_VALID_SIGNATURES: \"$min_valid\"/" docker-compose.yml
    
    # Start services
    echo "🚀 Starting services..."
    docker-compose up -d central node1-api node1-redis node2-api node2-redis > /dev/null 2>&1
    
    # Wait for services
    wait_for_service "Central" "http://localhost:8081/health" || {
        echo "Failed to start central"
        cleanup
        return 1
    }
    
    wait_for_service "Node1" "http://localhost:8001/health" || {
        echo "Failed to start node1"
        cleanup
        return 1
    }
    
    wait_for_service "Node2" "http://localhost:8002/health" || {
        echo "Failed to start node2"
        cleanup
        return 1
    }
    
    sleep 5
    
    # Start Flower server
    echo "🌸 Starting Flower server..."
    docker-compose up -d central > /dev/null 2>&1
    docker-compose exec -d central python -m app.flower_server
    
    sleep 5
    
    # Start workers
    echo "👷 Starting workers..."
    docker-compose up -d node1-worker node2-worker > /dev/null 2>&1
    
    # Monitor logs
    echo ""
    echo "📊 Monitoring FL execution..."
    echo ""
    
    # Wait for completion (max 3 minutes)
    local timeout=180
    local elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        # Check if training is complete
        if docker-compose logs central 2>&1 | grep -q "FL training complete"; then
            echo ""
            echo -e "${GREEN}✓ Training completed${NC}"
            break
        fi
        
        # Check for errors
        if docker-compose logs central 2>&1 | grep -q "Error\|Failed"; then
            echo ""
            echo -e "${RED}✗ Training failed${NC}"
            break
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
        
        # Show progress every 15 seconds
        if [ $((elapsed % 15)) -eq 0 ]; then
            echo "  ... still running ($elapsed seconds elapsed)"
        fi
    done
    
    # Extract and display results
    echo ""
    echo "========================================================================"
    echo "📊 RESULTS FOR: $test_name"
    echo "========================================================================"
    
    # Show signature verification stats
    echo ""
    echo "🔐 Signature Verification:"
    docker-compose logs central 2>&1 | grep -A 5 "Signature Verification Stats" | tail -6
    
    # Show policy actions
    echo ""
    echo "📋 Policy Actions:"
    docker-compose logs central 2>&1 | grep "Policy:" || echo "  No policy actions logged"
    
    # Show aggregation results
    echo ""
    echo "📈 Aggregation Results:"
    docker-compose logs central 2>&1 | grep -E "ROUND.*COMPLETE|Aggregated" | tail -10
    
    # Cleanup
    cleanup
    
    # Restore original docker-compose.yml
    mv docker-compose.yml.backup docker-compose.yml
    
    echo ""
    echo -e "${GREEN}✓ Test completed${NC}"
    echo ""
    
    # Wait before next test
    sleep 5
}

# Main test execution
echo "This script will test 3 security policies:"
echo "  1. LOG policy - logs invalid signatures but continues"
echo "  2. WARN policy - warns if too many invalid signatures"
echo "  3. REJECT policy - excludes clients with invalid signatures"
echo ""
echo "Press Enter to continue or Ctrl+C to cancel..."
read

# Initial cleanup
cleanup

# Test 1: LOG policy (most permissive)
run_policy_test "log" "0.8" "LOG Policy - Permissive Mode"

# Test 2: WARN policy (balanced)
run_policy_test "warn" "0.8" "WARN Policy - Balanced Mode"

# Test 3: REJECT policy (strict)
run_policy_test "reject" "1.0" "REJECT Policy - Strict Mode"

echo ""
echo "========================================================================"
echo "🎉 ALL SECURITY POLICY TESTS COMPLETED"
echo "========================================================================"
echo ""
echo "Summary:"
echo "  ✓ LOG policy test completed"
echo "  ✓ WARN policy test completed"
echo "  ✓ REJECT policy test completed"
echo ""
echo "Review the results above to see how each policy behaves."
echo ""
