#!/bin/bash

# Start Fed-Med-FL with GPU Support
# Prerequisites:
#   1. NVIDIA GPU with CUDA support
#   2. NVIDIA Docker runtime installed
#   3. Docker with GPU support

set -e

echo "=========================================="
echo "Fed-Med-FL - GPU Mode"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ ERROR: Docker is not running!"
    echo "Please start Docker first."
    exit 1
fi

# Check NVIDIA GPU support
echo "Checking NVIDIA GPU support..."
if docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi > /dev/null 2>&1; then
    echo "✓ GPU detected! Starting with GPU support..."
    USE_GPU=yes
else
    echo ""
    echo "⚠️  WARNING: NVIDIA GPU not detected or Docker GPU support not configured!"
    echo ""
    echo "To enable GPU support:"
    echo "  1. Install NVIDIA Container Toolkit:"
    echo "     https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    echo "  2. Restart Docker"
    echo ""
    echo "Continuing with CPU mode..."
    echo ""
    USE_GPU=no
fi

echo ""
echo "Stopping existing containers..."
docker compose down

echo ""
echo "Building images..."
if [ "$USE_GPU" = "yes" ]; then
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml build
else
    docker compose build
fi

echo ""
echo "Starting services..."
if [ "$USE_GPU" = "yes" ]; then
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
else
    docker compose up -d
fi

echo ""
echo "Waiting for services to start..."
sleep 30

echo ""
echo "=========================================="
echo "Services Started!"
echo "=========================================="
echo ""
echo "Central Server: http://localhost:8080"
echo "Node1 UI:       http://localhost:3001"
echo "Node2 UI:       http://localhost:3002"
echo "Node3 UI:       http://localhost:3003"
echo ""
if [ "$USE_GPU" = "yes" ]; then
    echo "GPU Mode: ✓ ENABLED"
else
    echo "GPU Mode: ✗ DISABLED (using CPU)"
fi
echo ""
echo "View logs: docker compose logs -f"
echo "Stop: docker compose down"
echo ""
