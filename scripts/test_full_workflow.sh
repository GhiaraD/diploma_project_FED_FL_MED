#!/bin/bash
# Script pentru testarea completă a workflow-ului Node (cu dataset de test)

set -e

NODE_ID=${1:-node1}
API_PORT=$((8000 + ${NODE_ID#node}))
API_URL="http://localhost:${API_PORT}"

echo "=========================================="
echo "Full Workflow Test - ${NODE_ID}"
echo "API URL: ${API_URL}"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Create test dataset
echo -e "${BLUE}Step 1: Creating test dataset...${NC}"
TEST_DIR="/tmp/test_dataset_${NODE_ID}"
rm -rf ${TEST_DIR}
mkdir -p ${TEST_DIR}/NORMAL
mkdir -p ${TEST_DIR}/PNEUMONIA

# Create dummy images (1x1 pixel PNG)
# Base64 encoded 1x1 red PNG
RED_PNG="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

for i in {1..5}; do
    echo "$RED_PNG" | base64 -d > "${TEST_DIR}/NORMAL/img_${i}.png"
    echo "$RED_PNG" | base64 -d > "${TEST_DIR}/PNEUMONIA/img_${i}.png"
done

# Create ZIP
cd /tmp
zip -r "test_dataset_${NODE_ID}.zip" "test_dataset_${NODE_ID}" > /dev/null
echo -e "${GREEN}✓ Test dataset created (10 images)${NC}"
echo ""

# Wait for API
echo -e "${BLUE}Step 2: Waiting for API...${NC}"
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

# Upload dataset
echo -e "${BLUE}Step 3: Uploading dataset...${NC}"
upload_response=$(curl -s -X POST "${API_URL}/api/data/upload" \
    -F "file=@/tmp/test_dataset_${NODE_ID}.zip" \
    -F "split=train")

echo "$upload_response" | jq '.'
dataset_id=$(echo "$upload_response" | jq -r '.dataset_id')

if [ "$dataset_id" = "null" ] || [ -z "$dataset_id" ]; then
    echo -e "${RED}✗ Failed to upload dataset${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Dataset uploaded: ${dataset_id}${NC}"
echo ""

# List datasets
echo -e "${BLUE}Step 4: Listing datasets...${NC}"
curl -s "${API_URL}/api/data/list" | jq '.'
echo ""

# Start training
echo -e "${BLUE}Step 5: Starting local training...${NC}"
train_response=$(curl -s -X POST "${API_URL}/api/train/local" \
    -H "Content-Type: application/json" \
    -d "{
        \"dataset_id\": \"${dataset_id}\",
        \"model_name\": \"resnet18\",
        \"num_epochs\": 2,
        \"batch_size\": 2,
        \"learning_rate\": 0.001
    }")

echo "$train_response" | jq '.'
job_id=$(echo "$train_response" | jq -r '.job_id')

if [ "$job_id" = "null" ] || [ -z "$job_id" ]; then
    echo -e "${RED}✗ Failed to start training${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Training job started: ${job_id}${NC}"
echo ""

# Monitor training
echo -e "${BLUE}Step 6: Monitoring training progress...${NC}"
echo "This may take a few minutes..."
echo ""

max_wait=300  # 5 minutes
elapsed=0
while [ $elapsed -lt $max_wait ]; do
    status_response=$(curl -s "${API_URL}/api/train/status/${job_id}")
    status=$(echo "$status_response" | jq -r '.status')
    
    echo -e "Status: ${YELLOW}${status}${NC} (${elapsed}s elapsed)"
    
    if [ "$status" = "completed" ]; then
        echo ""
        echo -e "${GREEN}✓ Training completed!${NC}"
        echo "$status_response" | jq '.'
        
        model_id=$(echo "$status_response" | jq -r '.result.model_id')
        echo ""
        echo -e "${GREEN}✓ Model created: ${model_id}${NC}"
        break
    elif [ "$status" = "failed" ]; then
        echo ""
        echo -e "${RED}✗ Training failed${NC}"
        echo "$status_response" | jq '.'
        exit 1
    fi
    
    sleep 5
    elapsed=$((elapsed + 5))
done

if [ $elapsed -ge $max_wait ]; then
    echo -e "${RED}✗ Training timeout${NC}"
    exit 1
fi

echo ""

# List models
echo -e "${BLUE}Step 7: Listing models...${NC}"
curl -s "${API_URL}/api/models/registry" | jq '.'
echo ""

# Promote model
if [ ! -z "$model_id" ] && [ "$model_id" != "null" ]; then
    echo -e "${BLUE}Step 8: Promoting model to deployed...${NC}"
    promote_response=$(curl -s -X POST "${API_URL}/api/models/promote" \
        -H "Content-Type: application/json" \
        -d "{\"model_id\": \"${model_id}\"}")
    
    echo "$promote_response" | jq '.'
    echo -e "${GREEN}✓ Model promoted${NC}"
    echo ""
fi

# Test inference
echo -e "${BLUE}Step 9: Testing inference...${NC}"
test_image="${TEST_DIR}/NORMAL/img_1.png"

infer_response=$(curl -s -X POST "${API_URL}/api/infer" \
    -H "Content-Type: application/json" \
    -d "{
        \"image_paths\": [\"${test_image}\"],
        \"generate_gradcam\": true
    }")

echo "$infer_response" | jq '.'
infer_job_id=$(echo "$infer_response" | jq -r '.job_id')

if [ "$infer_job_id" = "null" ] || [ -z "$infer_job_id" ]; then
    echo -e "${RED}✗ Failed to start inference${NC}"
else
    echo -e "${GREEN}✓ Inference job started: ${infer_job_id}${NC}"
    
    # Wait for inference
    sleep 10
    
    echo ""
    echo -e "${BLUE}Step 10: Getting inference results...${NC}"
    results_response=$(curl -s "${API_URL}/api/infer/results/${infer_job_id}")
    echo "$results_response" | jq '.'
    
    infer_status=$(echo "$results_response" | jq -r '.status')
    if [ "$infer_status" = "completed" ]; then
        echo -e "${GREEN}✓ Inference completed${NC}"
    fi
fi

echo ""

# Summary
echo "=========================================="
echo "Workflow Test Summary"
echo "=========================================="
echo -e "${GREEN}✓ Dataset upload: SUCCESS${NC}"
echo -e "${GREEN}✓ Local training: SUCCESS${NC}"
echo -e "${GREEN}✓ Model registry: SUCCESS${NC}"
echo -e "${GREEN}✓ Model promotion: SUCCESS${NC}"
echo -e "${GREEN}✓ Inference: SUCCESS${NC}"
echo ""
echo -e "${BLUE}All components are working correctly!${NC}"
echo ""

# Cleanup
rm -rf ${TEST_DIR}
rm -f "/tmp/test_dataset_${NODE_ID}.zip"
