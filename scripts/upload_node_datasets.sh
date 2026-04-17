#!/bin/bash

# Upload Node Datasets to FL Platform
# Usage: ./scripts/upload_node_datasets.sh

set -e

DATASET_DIR="/home/student/disertatie/diploma_project_FED_FL_MED/fl_datasets"

echo "=========================================="
echo "Uploading Node Datasets to FL Platform"
echo "=========================================="
echo ""

# Check if services are running
echo "▶ Checking services..."
for port in 8001 8002 8003; do
    if ! curl -s http://localhost:$port/api/health > /dev/null 2>&1; then
        echo "❌ Node on port $port is not running"
        echo "Run: make up"
        exit 1
    fi
done
echo "✓ All nodes are running"
echo ""

# Upload to each node
echo "▶ Uploading datasets..."
echo ""

# Node1
echo "Node 1 (http://localhost:8001):"
echo -n "  Uploading node1_train.zip (356MB)... "
RESPONSE=$(curl -s -X POST http://localhost:8001/api/data/upload \
    -F "file=@${DATASET_DIR}/node1_train.zip" \
    -F "split=train")

if echo "$RESPONSE" | grep -q "dataset_id"; then
    DATASET_ID_1=$(echo $RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
    echo "✓"
    echo "  Dataset ID: $DATASET_ID_1"
else
    echo "❌ Failed"
    echo "  Response: $RESPONSE"
    exit 1
fi
echo ""

# Node2
echo "Node 2 (http://localhost:8002):"
echo -n "  Uploading node2_train.zip (375MB)... "
RESPONSE=$(curl -s -X POST http://localhost:8002/api/data/upload \
    -F "file=@${DATASET_DIR}/node2_train.zip" \
    -F "split=train")

if echo "$RESPONSE" | grep -q "dataset_id"; then
    DATASET_ID_2=$(echo $RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
    echo "✓"
    echo "  Dataset ID: $DATASET_ID_2"
else
    echo "❌ Failed"
    echo "  Response: $RESPONSE"
    exit 1
fi
echo ""

# Node3
echo "Node 3 (http://localhost:8003):"
echo -n "  Uploading node3_train.zip (360MB)... "
RESPONSE=$(curl -s -X POST http://localhost:8003/api/data/upload \
    -F "file=@${DATASET_DIR}/node3_train.zip" \
    -F "split=train")

if echo "$RESPONSE" | grep -q "dataset_id"; then
    DATASET_ID_3=$(echo $RESPONSE | grep -o '"dataset_id":"[^"]*"' | cut -d'"' -f4)
    echo "✓"
    echo "  Dataset ID: $DATASET_ID_3"
else
    echo "❌ Failed"
    echo "  Response: $RESPONSE"
    exit 1
fi
echo ""

# Summary
echo "=========================================="
echo "Upload Complete!"
echo "=========================================="
echo ""
echo "Dataset IDs (save these for FL training):"
echo "  node1: $DATASET_ID_1"
echo "  node2: $DATASET_ID_2"
echo "  node3: $DATASET_ID_3"
echo ""
echo "Dataset Statistics:"
echo "  node1: 1738 images (447 NORMAL, 1291 PNEUMONIA)"
echo "  node2: 1738 images (447 NORMAL, 1291 PNEUMONIA)"
echo "  node3: 1740 images (447 NORMAL, 1293 PNEUMONIA)"
echo "  Total: 5216 images"
echo ""
echo "Next steps:"
echo "  1. Verify datasets in UI:"
echo "     - http://localhost:3001/studies"
echo "     - http://localhost:3002/studies"
echo "     - http://localhost:3003/studies"
echo ""
echo "  2. Create FL round:"
echo "     curl -X POST http://localhost:8080/round/create \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{"
echo "         \"round_id\": \"R-1\","
echo "         \"model_name\": \"resnet18\","
echo "         \"num_classes\": 2,"
echo "         \"pretrained\": true,"
echo "         \"hyperparameters\": {"
echo "           \"num_epochs\": 5,"
echo "           \"batch_size\": 32,"
echo "           \"learning_rate\": 0.001,"
echo "           \"optimizer\": \"adam\""
echo "         }"
echo "       }'"
echo ""
echo "  3. Start FL training on each node via UI (Federated page)"
echo ""
