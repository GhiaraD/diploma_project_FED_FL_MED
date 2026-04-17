#!/bin/bash
# Simple test for aggregation fix

CENTRAL_URL="http://localhost:8080"
ROUND_ID="R-FIX-TEST"

echo "============================================================"
echo "Testing Aggregation Fix for n_samples=0"
echo "============================================================"

# Submit mock updates (without actual delta, just to test metrics aggregation)
echo ""
echo "▶ Submitting mock update from node1..."
curl -X POST "$CENTRAL_URL/update/submit" \
  -H 'Content-Type: application/json' \
  -d '{
    "round_id": "'"$ROUND_ID"'",
    "node_id": "node1",
    "n_samples": 0,
    "metrics": {
      "accuracy": 0.9770,
      "f1": 0.9852,
      "precision": 0.9745,
      "recall": 0.9963,
      "auc": 0.9925
    },
    "delta": {},
    "model_hash": "test_hash_1"
  }' 2>/dev/null | python3 -m json.tool

echo ""
echo "▶ Submitting mock update from node2..."
curl -X POST "$CENTRAL_URL/update/submit" \
  -H 'Content-Type: application/json' \
  -d '{
    "round_id": "'"$ROUND_ID"'",
    "node_id": "node2",
    "n_samples": 0,
    "metrics": {
      "accuracy": 0.9856,
      "f1": 0.9905,
      "precision": 0.9886,
      "recall": 0.9924,
      "auc": 0.9986
    },
    "delta": {},
    "model_hash": "test_hash_2"
  }' 2>/dev/null | python3 -m json.tool

echo ""
echo "▶ Submitting mock update from node3..."
curl -X POST "$CENTRAL_URL/update/submit" \
  -H 'Content-Type: application/json' \
  -d '{
    "round_id": "'"$ROUND_ID"'",
    "node_id": "node3",
    "n_samples": 0,
    "metrics": {
      "accuracy": 0.9655,
      "f1": 0.9767,
      "precision": 0.9580,
      "recall": 0.9960,
      "auc": 0.9962
    },
    "delta": {},
    "model_hash": "test_hash_3"
  }' 2>/dev/null | python3 -m json.tool

echo ""
echo "▶ Triggering FedAvg aggregation..."
curl -X POST "$CENTRAL_URL/round/$ROUND_ID/aggregate" 2>/dev/null | python3 -m json.tool

echo ""
echo "============================================================"
echo "Expected (simple average since n_samples=0):"
echo "  accuracy:  0.9760"
echo "  f1:        0.9841"
echo "  precision: 0.9737"
echo "  recall:    0.9949"
echo "  auc:       0.9958"
echo "============================================================"
