#!/bin/bash
# Script pentru testarea Node API + Worker (Faza 3)

set -e

NODE_ID=${1:-node1}
API_PORT=$((8000 + ${NODE_ID#node}))
API_URL="http://localhost:${API_PORT}"

echo "=========================================="
echo "Testing Node API - ${NODE_ID}"
echo "API URL: ${API_URL}"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    
    echo -n "Testing ${name}... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "${API_URL}${endpoint}")
    else
        response=$(curl -s -w "\n%{http_code}" -X ${method} "${API_URL}${endpoint}" \
            -H "Content-Type: application/json" \
            -d "${data}")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "${GREEN}✓ OK${NC} (HTTP ${http_code})"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        echo ""
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP ${http_code})"
        echo "$body"
        echo ""
        return 1
    fi
}

# Wait for API to be ready
echo "Waiting for API to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s "${API_URL}/api/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API is ready${NC}"
        echo ""
        break
    fi
    attempt=$((attempt + 1))
    echo -n "."
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗ API failed to start${NC}"
    exit 1
fi

# Test 1: Health Check
echo "=========================================="
echo "Test 1: Health & Status"
echo "=========================================="
test_endpoint "Health Check" "GET" "/api/health"
test_endpoint "Node Status" "GET" "/api/node/status"

# Test 2: Dataset Management
echo "=========================================="
echo "Test 2: Dataset Management"
echo "=========================================="
test_endpoint "List Datasets" "GET" "/api/data/list"

# Test 3: Model Registry
echo "=========================================="
echo "Test 3: Model Registry"
echo "=========================================="
test_endpoint "List Models" "GET" "/api/models/registry"
test_endpoint "List Candidate Models" "GET" "/api/models/registry?type=candidate"
test_endpoint "List Deployed Models" "GET" "/api/models/registry?type=deployed"

# Test 4: Training (without actual dataset - will fail but tests endpoint)
echo "=========================================="
echo "Test 4: Training Endpoints"
echo "=========================================="
echo -e "${YELLOW}Note: Training will fail without dataset, but tests endpoint availability${NC}"
echo ""

# This will fail but shows the endpoint works
curl -s -X POST "${API_URL}/api/train/local" \
    -H "Content-Type: application/json" \
    -d '{
        "dataset_id": "test_dataset",
        "model_name": "resnet18",
        "num_epochs": 1,
        "batch_size": 8,
        "learning_rate": 0.001
    }' | jq '.' || echo "Expected failure - no dataset"
echo ""

# Test 5: Inference Endpoints
echo "=========================================="
echo "Test 5: Inference Endpoints"
echo "=========================================="
echo -e "${YELLOW}Note: Inference will fail without model, but tests endpoint availability${NC}"
echo ""

curl -s -X POST "${API_URL}/api/infer" \
    -H "Content-Type: application/json" \
    -d '{
        "image_paths": ["/storage/test.jpg"],
        "generate_gradcam": true
    }' | jq '.' || echo "Expected failure - no model"
echo ""

# Test 6: Federated Learning Endpoints
echo "=========================================="
echo "Test 6: Federated Learning Endpoints"
echo "=========================================="
echo -e "${YELLOW}Note: FL will fail without central server, but tests endpoint availability${NC}"
echo ""

curl -s -X POST "${API_URL}/api/federated/join/R-1" \
    -H "Content-Type: application/json" \
    -d '{}' | jq '.' || echo "Expected failure - no central server"
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}✓ Basic endpoints are working${NC}"
echo -e "${YELLOW}⚠ Full functionality requires:${NC}"
echo "  - Dataset upload"
echo "  - Central server (for FL)"
echo "  - Worker processing"
echo ""
echo "To test full workflow:"
echo "  1. Upload a dataset: curl -X POST -F 'file=@dataset.zip' ${API_URL}/api/data/upload"
echo "  2. Start training: curl -X POST ${API_URL}/api/train/local -d '{...}'"
echo "  3. Check job status: curl ${API_URL}/api/train/status/{job_id}"
echo ""
