#!/bin/bash

# Upload Real Datasets to Nodes
# Usage: ./scripts/upload_real_datasets.sh /path/to/dataset

set -e

DATASET_PATH=${1:-"./dataset"}

if [ ! -d "$DATASET_PATH" ]; then
    echo "❌ Dataset path not found: $DATASET_PATH"
    echo "Usage: $0 /path/to/dataset"
    exit 1
fi

echo "=========================================="
echo "Uploading Real Datasets to Nodes"
echo "=========================================="
echo ""

# Check if services are running
echo "▶ Checking services..."
for port in 8001 8002 8003; do
    if ! curl -s http://localhost:$port/api/health > /dev/null; then
        echo "❌ Node on port $port is not running"
        echo "Run: make up"
        exit 1
    fi
done
echo "✓ All nodes are running"
echo ""

# Create temporary ZIPs
echo "▶ Creating ZIP files..."
TEMP_DIR=$(mktemp -d)

# Node1 - train
cd "$DATASET_PATH/train"
zip -q -r "$TEMP_DIR/node1_train.zip" NORMAL/ PNEUMONIA/
echo "✓ node1_train.zip created"

# Node2 - val
cd "$DATASET_PATH/val"
zip -q -r "$TEMP_DIR/node2_val.zip" NORMAL/ PNEUMONIA/
echo "✓ node2_val.zip created"

# Node3 - test
cd "$DATASET_PATH/test"
zip -q -r "$TEMP_DIR/node3_test.zip" NORMAL/ PNEUMONIA/
echo "✓ node3_test.zip created"

cd - > /dev/null
echo ""

# Upload to nodes
echo "▶ Uploading datasets..."

# Node1
echo -n "  node1 (train): "
RESPONSE=$(curl -s -X POST http://localhost:8001/api/data/upload \
    -F "file=@$TEMP_DIR/node1_train.zip" \
    -F "split=train")
DATASET_ID_1=$(echo $RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
if [ -n "$DATASET_ID_1" ]; then
    echo "✓ $DATASET_ID_1"
else
    echo "❌ Failed"
    echo "Response: $RESPONSE"
fi

# Node2
echo -n "  node2 (val): "
RESPONSE=$(curl -s -X POST http://localhost:8002/api/data/upload \
    -F "file=@$TEMP_DIR/node2_val.zip" \
    -F "split=val")
DATASET_ID_2=$(echo $RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
if [ -n "$DATASET_ID_2" ]; then
    echo "✓ $DATASET_ID_2"
else
    echo "❌ Failed"
    echo "Response: $RESPONSE"
fi

# Node3
echo -n "  node3 (test): "
RESPONSE=$(curl -s -X POST http://localhost:8003/api/data/upload \
    -F "file=@$TEMP_DIR/node3_test.zip" \
    -F "split=test")
DATASET_ID_3=$(echo $RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
if [ -n "$DATASET_ID_3" ]; then
    echo "✓ $DATASET_ID_3"
else
    echo "❌ Failed"
    echo "Response: $RESPONSE"
fi

# Cleanup
rm -rf "$TEMP_DIR"
echo ""

# Summary
echo "=========================================="
echo "Upload Complete!"
echo "=========================================="
echo ""
echo "Dataset IDs:"
echo "  node1: $DATASET_ID_1"
echo "  node2: $DATASET_ID_2"
echo "  node3: $DATASET_ID_3"
echo ""
echo "Next steps:"
echo "  1. Create FL round: curl -X POST http://localhost:8080/round/create -d '{...}'"
echo "  2. Join round on each node"
echo "  3. Start training with dataset IDs above"
echo ""
