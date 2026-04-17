#!/bin/bash

# Monitor FL Training Progress
# Usage: ./scripts/monitor_fl_training.sh <job_id_node1> <job_id_node2> <job_id_node3>

set -e

JOB1=${1:-"fl_train_R-2_f25a32cd"}
JOB2=${2:-"fl_train_R-2_5f40a8c7"}
JOB3=${3:-"fl_train_R-2_ce57b313"}

echo "=========================================="
echo "FL Training Monitor"
echo "=========================================="
echo "Node1: $JOB1"
echo "Node2: $JOB2"
echo "Node3: $JOB3"
echo ""
echo "Press Ctrl+C to stop monitoring"
echo "=========================================="
echo ""

# Function to get status
get_status() {
    local port=$1
    local job_id=$2
    local node_name=$3
    
    response=$(curl -s http://localhost:$port/api/train/status/$job_id)
    status=$(echo $response | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null || echo "error")
    
    # Try to get error if failed
    if [ "$status" = "failed" ]; then
        error=$(echo $response | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('error', 'Unknown error')[:50])" 2>/dev/null || echo "Unknown")
        echo "$node_name: ❌ FAILED - $error"
    elif [ "$status" = "completed" ]; then
        # Try to get metrics
        metrics=$(echo $response | python3 -c "import sys, json; d=json.load(sys.stdin); r=d.get('result',{}); m=r.get('metrics',{}); print(f\"acc={m.get('accuracy',0):.3f}\")" 2>/dev/null || echo "")
        echo "$node_name: ✓ COMPLETED $metrics"
    elif [ "$status" = "running" ]; then
        echo "$node_name: ⏳ RUNNING..."
    elif [ "$status" = "pending" ]; then
        echo "$node_name: ⏸  PENDING"
    else
        echo "$node_name: ⚠  $status"
    fi
}

# Monitor loop
iteration=0
all_completed=false

while [ "$all_completed" = false ]; do
    iteration=$((iteration + 1))
    timestamp=$(date '+%H:%M:%S')
    
    echo "[$timestamp] Check #$iteration"
    echo "─────────────────────────────────────────"
    
    status1=$(get_status 8001 "$JOB1" "Node1")
    status2=$(get_status 8002 "$JOB2" "Node2")
    status3=$(get_status 8003 "$JOB3" "Node3")
    
    echo "$status1"
    echo "$status2"
    echo "$status3"
    
    # Check if all completed or failed
    if echo "$status1$status2$status3" | grep -q "RUNNING\|PENDING"; then
        echo ""
        echo "Training in progress... (checking again in 30s)"
        echo ""
        sleep 30
    else
        all_completed=true
        echo ""
        echo "=========================================="
        echo "All nodes finished!"
        echo "=========================================="
        
        # Check if all succeeded
        if echo "$status1$status2$status3" | grep -q "FAILED"; then
            echo "⚠️  Some nodes failed. Check logs:"
            echo "  docker compose logs node1-worker"
            echo "  docker compose logs node2-worker"
            echo "  docker compose logs node3-worker"
        else
            echo "✓ All nodes completed successfully!"
            echo ""
            echo "Next step: Trigger aggregation"
            echo "  curl -X POST http://localhost:8080/round/R-2/aggregate"
        fi
    fi
done
