#!/bin/bash
# Simple script to start Flower server in background

MODEL_NAME=$1
NUM_ROUNDS=${2:-1}
NUM_EPOCHS=${3:-2}

export MODEL_NAME="$MODEL_NAME"
export NUM_ROUNDS=$NUM_ROUNDS
export MIN_CLIENTS=2
export MIN_FIT_CLIENTS=2
export MIN_AVAILABLE_CLIENTS=2
export NUM_EPOCHS=$NUM_EPOCHS
export LEARNING_RATE=0.001
export OPTIMIZER='adam'
export FLOWER_SERVER_ADDRESS='0.0.0.0:8080'

python -m app.flower_server > /tmp/flower_${MODEL_NAME}.log 2>&1 &
echo $! > /tmp/flower_server.pid

echo "Flower server started with PID $(cat /tmp/flower_server.pid)"
