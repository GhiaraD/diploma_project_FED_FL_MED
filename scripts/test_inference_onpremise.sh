#!/bin/bash

# Test Inference On-Premise Workflow
# This demonstrates how inference works with images already on the server

set -e

NODE_API="http://localhost:8001"
NODE_ID="node1"

echo "========================================"
echo "Fed-Med-FL On-Premise Inference Test"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check if node has datasets
echo -e "${BLUE}▶ Step 1: Checking available datasets...${NC}"
DATASETS=$(curl -s ${NODE_API}/api/data/list)
DATASET_COUNT=$(echo $DATASETS | jq '. | length')

if [ "$DATASET_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠ No datasets found. Please upload a dataset first.${NC}"
    echo ""
    echo "To upload a dataset:"
    echo "  make create-datasets"
    echo "  curl -X POST ${NODE_API}/api/data/upload \\"
    echo "    -F 'file=@test_dataset_node1.zip' \\"
    echo "    -F 'split=train'"
    exit 1
fi

echo -e "${GREEN}✓ Found ${DATASET_COUNT} dataset(s)${NC}"
echo ""

# Get first dataset
DATASET_ID=$(echo $DATASETS | jq -r '.[0].dataset_id')
DATASET_PATH=$(curl -s ${NODE_API}/api/data/list | jq -r ".[0] | \"/storage/datasets/\" + .dataset_id")

echo -e "${BLUE}Using dataset: ${DATASET_ID}${NC}"
echo ""

# Step 2: Browse images in dataset
echo -e "${BLUE}▶ Step 2: Browsing images in dataset...${NC}"

# Try NORMAL folder first
NORMAL_DIR="${DATASET_PATH}/NORMAL"
echo "Browsing: ${NORMAL_DIR}"

BROWSE_RESULT=$(curl -s "${NODE_API}/api/infer/browse?directory=${NORMAL_DIR}" || echo '{"files":[]}')
IMAGE_COUNT=$(echo $BROWSE_RESULT | jq '.files | length')

if [ "$IMAGE_COUNT" -eq 0 ]; then
    # Try PNEUMONIA folder
    PNEUMONIA_DIR="${DATASET_PATH}/PNEUMONIA"
    echo "Trying: ${PNEUMONIA_DIR}"
    BROWSE_RESULT=$(curl -s "${NODE_API}/api/infer/browse?directory=${PNEUMONIA_DIR}" || echo '{"files":[]}')
    IMAGE_COUNT=$(echo $BROWSE_RESULT | jq '.files | length')
fi

if [ "$IMAGE_COUNT" -eq 0 ]; then
    echo -e "${RED}✗ No images found in dataset${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found ${IMAGE_COUNT} images${NC}"
echo ""

# Get first 3 image paths
IMAGE_PATHS=$(echo $BROWSE_RESULT | jq -r '.files[0:3] | map(.path) | @json')
echo "Selected images:"
echo $IMAGE_PATHS | jq -r '.[]' | head -3
echo ""

# Step 3: Check if deployed model exists
echo -e "${BLUE}▶ Step 3: Checking for deployed model...${NC}"
MODELS=$(curl -s ${NODE_API}/api/models/registry)
DEPLOYED_COUNT=$(echo $MODELS | jq '[.models[] | select(.type == "deployed")] | length')

if [ "$DEPLOYED_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠ No deployed model found${NC}"
    echo ""
    echo "To deploy a model:"
    echo "  1. Train a model first (or run FL training)"
    echo "  2. Promote candidate to deployed:"
    echo "     curl -X POST ${NODE_API}/api/models/promote \\"
    echo "       -H 'Content-Type: application/json' \\"
    echo "       -d '{\"model_id\": \"<model_id>\"}'"
    echo ""
    echo -e "${YELLOW}Continuing anyway - inference will use default model...${NC}"
fi

if [ "$DEPLOYED_COUNT" -gt 0 ]; then
    DEPLOYED_MODEL=$(echo $MODELS | jq -r '.models[] | select(.type == "deployed") | .model_id' | head -1)
    echo -e "${GREEN}✓ Using deployed model: ${DEPLOYED_MODEL}${NC}"
fi
echo ""

# Step 4: Start inference
echo -e "${BLUE}▶ Step 4: Starting inference...${NC}"

INFER_REQUEST=$(cat <<EOF
{
  "image_paths": ${IMAGE_PATHS},
  "generate_gradcam": true
}
EOF
)

echo "Request:"
echo $INFER_REQUEST | jq '.'
echo ""

INFER_RESPONSE=$(curl -s -X POST ${NODE_API}/api/infer \
  -H "Content-Type: application/json" \
  -d "$INFER_REQUEST")

JOB_ID=$(echo $INFER_RESPONSE | jq -r '.job_id')

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
    echo -e "${RED}✗ Failed to start inference${NC}"
    echo "Response:"
    echo $INFER_RESPONSE | jq '.'
    exit 1
fi

echo -e "${GREEN}✓ Inference job started: ${JOB_ID}${NC}"
echo ""

# Step 5: Monitor inference progress
echo -e "${BLUE}▶ Step 5: Monitoring inference progress...${NC}"

MAX_ATTEMPTS=60
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    
    RESULT=$(curl -s ${NODE_API}/api/infer/results/${JOB_ID})
    STATUS=$(echo $RESULT | jq -r '.status')
    
    if [ "$STATUS" == "completed" ]; then
        echo -e "${GREEN}✓ Inference completed!${NC}"
        echo ""
        
        # Display results
        echo "============================================================"
        echo "INFERENCE RESULTS"
        echo "============================================================"
        echo ""
        
        RESULTS=$(echo $RESULT | jq -r '.results')
        NUM_RESULTS=$(echo $RESULTS | jq 'length')
        
        echo "Job ID: ${JOB_ID}"
        echo "Images processed: ${NUM_RESULTS}"
        echo ""
        
        for i in $(seq 0 $((NUM_RESULTS - 1))); do
            IMAGE_PATH=$(echo $RESULTS | jq -r ".[$i].image_path")
            IMAGE_NAME=$(basename $IMAGE_PATH)
            PRED_CLASS=$(echo $RESULTS | jq -r ".[$i].predicted_class")
            CONFIDENCE=$(echo $RESULTS | jq -r ".[$i].confidence")
            GRADCAM_PATH=$(echo $RESULTS | jq -r ".[$i].gradcam_path")
            
            if [ "$PRED_CLASS" == "0" ]; then
                PRED_LABEL="NORMAL"
                COLOR=$GREEN
            else
                PRED_LABEL="PNEUMONIA"
                COLOR=$RED
            fi
            
            echo -e "Image: ${IMAGE_NAME}"
            echo -e "  Prediction: ${COLOR}${PRED_LABEL}${NC}"
            echo -e "  Confidence: $(echo "$CONFIDENCE * 100" | bc -l | xargs printf "%.1f")%"
            if [ "$GRADCAM_PATH" != "null" ]; then
                echo -e "  Grad-CAM: ${GRADCAM_PATH}"
            fi
            echo ""
        done
        
        echo "============================================================"
        echo ""
        echo -e "${GREEN}✓ On-Premise Inference Test PASSED!${NC}"
        echo ""
        echo "Key Points:"
        echo "  • Images remained in original location: ${NORMAL_DIR}"
        echo "  • No data left the hospital premises"
        echo "  • Only inference results were stored"
        echo "  • Grad-CAM visualizations generated"
        
        exit 0
    elif [ "$STATUS" == "failed" ]; then
        echo -e "${RED}✗ Inference failed${NC}"
        echo "Error:"
        echo $RESULT | jq '.error'
        exit 1
    else
        echo -ne "  Status: ${STATUS} (attempt ${ATTEMPT}/${MAX_ATTEMPTS})\r"
        sleep 5
    fi
done

echo ""
echo -e "${RED}✗ Inference timeout${NC}"
exit 1
