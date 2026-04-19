#!/bin/bash
# Simple Inference Test on Node1

set -e

NODE_URL="http://localhost:8001"
TEST_IMAGE="/home/student/disertatie/dataset/chest_xray/test/NORMAL/IM-0001-0001.jpeg"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================================"
echo "Testing Inference on Node1"
echo "============================================================"
echo ""

# Step 1: Check if test image exists
echo -e "${BLUE}▶ Step 1: Checking test image...${NC}"
if [ ! -f "$TEST_IMAGE" ]; then
    echo -e "  ${YELLOW}✗${NC} Test image not found: $TEST_IMAGE"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Test image found: $(basename $TEST_IMAGE)"
echo "  Expected: NORMAL (healthy chest X-ray)"

# Step 2: Check deployed model
echo ""
echo -e "${BLUE}▶ Step 2: Checking deployed model...${NC}"
MODELS=$(curl -s "$NODE_URL/api/models/registry")
DEPLOYED_MODEL=$(echo "$MODELS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
deployed = [m for m in data['models'] if m['type'] == 'deployed']
if deployed:
    m = deployed[0]
    print(f\"{m['model_id']}\")
    print(f\"Accuracy: {m['metrics'].get('accuracy', 0):.2%}\", file=sys.stderr)
else:
    print('NONE')
" 2>&1)

if echo "$DEPLOYED_MODEL" | grep -q "NONE"; then
    echo -e "  ${YELLOW}✗${NC} No deployed model found!"
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Deployed model: $(echo "$DEPLOYED_MODEL" | head -1)"
echo "  $(echo "$DEPLOYED_MODEL" | tail -1)"

# Step 3: Run inference
echo ""
echo -e "${BLUE}▶ Step 3: Running inference...${NC}"

INFER_RESPONSE=$(curl -s -X POST "$NODE_URL/api/infer" \
  -F "images=@$TEST_IMAGE")

if echo "$INFER_RESPONSE" | grep -q "job_id"; then
    JOB_ID=$(echo "$INFER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
    echo -e "  ${GREEN}✓${NC} Inference started (Job ID: $JOB_ID)"
else
    echo -e "  ${YELLOW}✗${NC} Failed to start inference"
    echo "$INFER_RESPONSE" | python3 -m json.tool
    exit 1
fi

# Step 4: Monitor progress
echo ""
echo -e "${BLUE}▶ Step 4: Waiting for results...${NC}"
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
    
    if not results:
        print('No results found')
        sys.exit(1)
    
    result = results[0]
    
    print(f'Image: {result[\"image_name\"]}')
    print(f'Ground Truth: NORMAL (healthy)')
    print()
    print(f'Prediction: {result[\"prediction\"]}')
    print(f'Confidence: {result[\"confidence\"]:.2%}')
    print()
    print('Probabilities:')
    for cls, prob in result['probabilities'].items():
        bar = '█' * int(prob * 50)
        print(f'  {cls:12s}: {prob:.4f} {bar}')
    print()
    
    if result.get('gradcam_path'):
        print(f'Grad-CAM saved: {result[\"gradcam_path\"]}')
    
    # Check if prediction is correct
    prediction = result['prediction']
    if prediction == 'NORMAL':
        print()
        print('✓ CORRECT PREDICTION!')
    else:
        print()
        print('✗ INCORRECT PREDICTION (expected NORMAL)')
        
except Exception as e:
    print(f'Error parsing results: {e}')
    import traceback
    traceback.print_exc()
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

echo ""
echo -e "${GREEN}✓ Inference test completed!${NC}"
echo ""
