#!/bin/bash
# Test Inference on Node1

set -e

NODE_URL="http://localhost:8001"
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================================"
echo "Testing Inference on Node1"
echo "============================================================"
echo ""

# Step 1: Get available models
echo -e "${BLUE}▶ Step 1: Getting available models...${NC}"
MODELS=$(curl -s "$NODE_URL/api/models/registry")
echo "$MODELS" | python3 -m json.tool | head -50

# Step 2: Check if there's a deployed model
echo ""
echo -e "${BLUE}▶ Step 2: Checking for deployed model...${NC}"
DEPLOYED_MODEL=$(echo "$MODELS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
deployed = [m for m in data['models'] if m['type'] == 'deployed']
if deployed:
    print(deployed[0]['model_id'])
else:
    print('NONE')
" 2>/dev/null || echo "NONE")

if [ "$DEPLOYED_MODEL" = "NONE" ]; then
    echo -e "  ${YELLOW}⚠${NC} No deployed model found. Promoting best candidate..."
    
    # Get best candidate model (highest accuracy)
    BEST_MODEL=$(echo "$MODELS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
candidates = [m for m in data['models'] if m['type'] == 'candidate' and m.get('metrics')]
if candidates:
    best = max(candidates, key=lambda x: x['metrics'].get('accuracy', 0))
    print(best['model_id'])
else:
    print('NONE')
" 2>/dev/null || echo "NONE")
    
    if [ "$BEST_MODEL" = "NONE" ]; then
        echo -e "  ${YELLOW}✗${NC} No candidate models available!"
        exit 1
    fi
    
    echo "  Promoting model: $BEST_MODEL"
    
    PROMOTE_RESPONSE=$(curl -s -X POST "$NODE_URL/api/models/promote" \
      -H 'Content-Type: application/json' \
      -d "{\"model_id\": \"$BEST_MODEL\"}")
    
    if echo "$PROMOTE_RESPONSE" | grep -q "success"; then
        echo -e "  ${GREEN}✓${NC} Model promoted to deployed"
        DEPLOYED_MODEL=$BEST_MODEL
    else
        echo -e "  ${YELLOW}✗${NC} Failed to promote model"
        echo "$PROMOTE_RESPONSE"
        exit 1
    fi
else
    echo -e "  ${GREEN}✓${NC} Deployed model found: $DEPLOYED_MODEL"
fi

# Step 3: Get test images
echo ""
echo -e "${BLUE}▶ Step 3: Preparing test images...${NC}"

# Check if we have test images in the dataset
TEST_IMAGES_DIR="fl_datasets/node1/train/NORMAL"
if [ ! -d "$TEST_IMAGES_DIR" ]; then
    echo -e "  ${YELLOW}✗${NC} Test images directory not found: $TEST_IMAGES_DIR"
    exit 1
fi

# Get first 3 images
TEST_IMAGES=($(ls "$TEST_IMAGES_DIR"/*.jpeg 2>/dev/null | head -3))

if [ ${#TEST_IMAGES[@]} -eq 0 ]; then
    echo -e "  ${YELLOW}✗${NC} No test images found"
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Found ${#TEST_IMAGES[@]} test images"
for img in "${TEST_IMAGES[@]}"; do
    echo "    - $(basename $img)"
done

# Step 4: Run inference
echo ""
echo -e "${BLUE}▶ Step 4: Running inference...${NC}"

# Create a temporary directory for copying images
TEMP_DIR="/tmp/inference_test_$$"
mkdir -p "$TEMP_DIR"

# Copy images to temp directory
for img in "${TEST_IMAGES[@]}"; do
    cp "$img" "$TEMP_DIR/"
done

echo "  Uploading images and running inference..."

# Build curl command with multiple files
CURL_CMD="curl -s -X POST \"$NODE_URL/api/infer\""
for img in "$TEMP_DIR"/*.jpeg; do
    CURL_CMD="$CURL_CMD -F \"images=@$img\""
done

# Execute inference
INFER_RESPONSE=$(eval $CURL_CMD)

# Clean up temp directory
rm -rf "$TEMP_DIR"

# Check response
if echo "$INFER_RESPONSE" | grep -q "job_id"; then
    JOB_ID=$(echo "$INFER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
    echo -e "  ${GREEN}✓${NC} Inference started (Job ID: $JOB_ID)"
    
    # Step 5: Monitor inference progress
    echo ""
    echo -e "${BLUE}▶ Step 5: Monitoring inference progress...${NC}"
    echo -n "  Progress: "
    
    MAX_WAIT=60
    ELAPSED=0
    
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        STATUS_RESPONSE=$(curl -s "$NODE_URL/api/infer/results/$JOB_ID")
        STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        
        if [ "$STATUS" = "completed" ]; then
            echo ""
            echo -e "  ${GREEN}✓${NC} Inference completed!"
            
            # Display results
            echo ""
            echo "============================================================"
            echo "INFERENCE RESULTS"
            echo "============================================================"
            echo "$STATUS_RESPONSE" | python3 -c "
import sys, json

try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    
    print(f'Total images: {len(results)}')
    print()
    
    for i, result in enumerate(results, 1):
        print(f'Image {i}: {result[\"image_name\"]}')
        print(f'  Prediction: {result[\"prediction\"]} ({result[\"confidence\"]:.2%} confidence)')
        print(f'  Probabilities:')
        for cls, prob in result['probabilities'].items():
            print(f'    {cls}: {prob:.4f}')
        if result.get('gradcam_path'):
            print(f'  Grad-CAM: {result[\"gradcam_path\"]}')
        print()
        
except Exception as e:
    print(f'Could not parse results: {e}')
    print(sys.stdin.read())
"
            echo "============================================================"
            break
        elif [ "$STATUS" = "failed" ]; then
            echo ""
            echo -e "  ${YELLOW}✗${NC} Inference failed!"
            echo "$STATUS_RESPONSE" | python3 -m json.tool
            exit 1
        else
            echo -n "."
            sleep 2
            ELAPSED=$((ELAPSED + 2))
        fi
    done
    
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo ""
        echo -e "  ${YELLOW}⚠${NC} Inference timeout"
        exit 1
    fi
    
else
    echo -e "  ${YELLOW}✗${NC} Failed to start inference"
    echo "$INFER_RESPONSE"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Inference test completed successfully!${NC}"
echo ""
