#!/bin/bash

# Test complete inference workflow
# Tests both NORMAL and PNEUMONIA images

set -e

echo "=========================================="
echo "Testing Inference Functionality"
echo "=========================================="
echo ""

# Test 1: NORMAL image
echo "Test 1: Inference on NORMAL image"
echo "------------------------------------------"
NORMAL_IMAGE="/storage/datasets/dataset_train_477f2544/train/NORMAL/IM-0119-0001.jpeg"

echo "Submitting inference job for NORMAL image..."
RESPONSE=$(curl -s -X POST http://localhost:8001/api/infer \
  -H "Content-Type: application/json" \
  -d "{
    \"image_paths\": [\"$NORMAL_IMAGE\"],
    \"generate_gradcam\": true
  }")

JOB_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

echo "Waiting for inference to complete..."
sleep 10

echo "Fetching results..."
curl -s http://localhost:8001/api/infer/results/$JOB_ID | python3 -m json.tool

echo ""
echo ""

# Test 2: PNEUMONIA image
echo "Test 2: Inference on PNEUMONIA image"
echo "------------------------------------------"
PNEUMONIA_IMAGE="/storage/datasets/dataset_train_477f2544/train/PNEUMONIA/person1000_bacteria_2931.jpeg"

echo "Submitting inference job for PNEUMONIA image..."
RESPONSE=$(curl -s -X POST http://localhost:8001/api/infer \
  -H "Content-Type: application/json" \
  -d "{
    \"image_paths\": [\"$PNEUMONIA_IMAGE\"],
    \"generate_gradcam\": true
  }")

JOB_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

echo "Waiting for inference to complete..."
sleep 10

echo "Fetching results..."
curl -s http://localhost:8001/api/infer/results/$JOB_ID | python3 -m json.tool

echo ""
echo ""

# Test 3: Batch inference
echo "Test 3: Batch inference on multiple images"
echo "------------------------------------------"

echo "Submitting batch inference job..."
RESPONSE=$(curl -s -X POST http://localhost:8001/api/infer \
  -H "Content-Type: application/json" \
  -d "{
    \"image_paths\": [
      \"$NORMAL_IMAGE\",
      \"$PNEUMONIA_IMAGE\"
    ],
    \"generate_gradcam\": true
  }")

JOB_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

echo "Waiting for inference to complete..."
sleep 10

echo "Fetching results..."
curl -s http://localhost:8001/api/infer/results/$JOB_ID | python3 -m json.tool

echo ""
echo "=========================================="
echo "✓ All inference tests completed!"
echo "=========================================="
