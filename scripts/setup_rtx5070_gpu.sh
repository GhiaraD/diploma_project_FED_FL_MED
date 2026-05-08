#!/bin/bash

# ============================================
# RTX 5070 GPU Setup Script
# ============================================
# 
# This script builds Docker images with PyTorch
# nightly (CUDA 13.2) for RTX 5070 support
#
# Date: May 6, 2026
# ============================================

set -e  # Exit on error

echo "=============================================="
echo "RTX 5070 GPU Setup - PyTorch CUDA 13.2"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# ============================================
# 1. Verify GPU
# ============================================
print_status "Verifying NVIDIA GPU..."

if ! command -v nvidia-smi &> /dev/null; then
    print_error "nvidia-smi not found. GPU support not available."
    exit 1
fi

GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}')

print_success "GPU detected: $GPU_NAME"
print_success "Driver: $DRIVER_VERSION"
print_success "CUDA: $CUDA_VERSION"

if [[ ! "$GPU_NAME" =~ "RTX 5070" ]]; then
    print_warning "GPU is not RTX 5070. This script is optimized for RTX 5070."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# ============================================
# 2. Verify Docker
# ============================================
print_status "Verifying Docker..."

if ! docker ps &> /dev/null; then
    print_error "Docker daemon not accessible. Start Docker Desktop."
    exit 1
fi

DOCKER_VERSION=$(docker --version)
print_success "Docker: $DOCKER_VERSION"
echo ""

# ============================================
# 3. Stop Existing Services
# ============================================
print_status "Stopping existing services..."
docker compose down 2>/dev/null || true
print_success "Services stopped"
echo ""

# ============================================
# 4. Build Images with PyTorch CUDA 13.2
# ============================================
print_status "Building Docker images with PyTorch nightly (CUDA 13.2)..."
print_warning "This will take 10-15 minutes (downloading PyTorch ~2GB per image)"
echo ""

# Build central
print_status "Building central server..."
docker compose build --no-cache central
print_success "Central server built"
echo ""

# Build node workers (these need GPU support)
print_status "Building node1-worker..."
docker compose build --no-cache node1-worker
print_success "Node1-worker built"
echo ""

print_status "Building node2-worker..."
docker compose build --no-cache node2-worker
print_success "Node2-worker built"
echo ""

print_status "Building node3-worker..."
docker compose build --no-cache node3-worker
print_success "Node3-worker built"
echo ""

# Build node APIs
print_status "Building node APIs..."
docker compose build --no-cache node1-api node2-api node3-api
print_success "Node APIs built"
echo ""

# Build UIs (optional, can skip for faster setup)
read -p "Build UIs? (y/n) [default: n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Building UIs..."
    docker compose build --no-cache node1-ui node2-ui node3-ui
    print_success "UIs built"
else
    print_warning "Skipping UI build. You can build later with: make build-ui"
fi
echo ""

# ============================================
# 5. Start Services
# ============================================
print_status "Starting services..."
docker compose up -d
print_success "Services started"
echo ""

# Wait for services to initialize
print_status "Waiting for services to initialize (30 seconds)..."
sleep 30
print_success "Services should be ready"
echo ""

# ============================================
# 6. Verify GPU Detection in Container
# ============================================
print_status "Verifying GPU detection in container..."
echo ""

GPU_TEST=$(docker compose exec -T node1-worker python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU count: {torch.cuda.device_count()}')
    print(f'GPU name: {torch.cuda.get_device_name(0)}')
    print(f'GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB')
else:
    print('ERROR: CUDA not available!')
" 2>&1)

echo "$GPU_TEST"
echo ""

if echo "$GPU_TEST" | grep -q "CUDA available: True"; then
    print_success "GPU detected successfully in container!"
    
    # Extract GPU name
    GPU_IN_CONTAINER=$(echo "$GPU_TEST" | grep "GPU name:" | cut -d: -f2 | xargs)
    print_success "Container sees: $GPU_IN_CONTAINER"
else
    print_error "GPU NOT detected in container!"
    print_error "This might be a Docker/NVIDIA runtime issue."
    echo ""
    print_status "Troubleshooting steps:"
    echo "  1. Verify nvidia-container-toolkit is installed"
    echo "  2. Restart Docker Desktop"
    echo "  3. Check Docker Desktop → Settings → Resources → WSL Integration"
    echo "  4. Run: docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi"
    exit 1
fi

echo ""

# ============================================
# 7. Test PyTorch Compute Capability
# ============================================
print_status "Testing PyTorch compute capability..."
echo ""

COMPUTE_TEST=$(docker compose exec -T node1-worker python -c "
import torch
if torch.cuda.is_available():
    props = torch.cuda.get_device_properties(0)
    print(f'Compute capability: {props.major}.{props.minor}')
    
    # Test tensor operations
    x = torch.randn(100, 100).cuda()
    y = torch.randn(100, 100).cuda()
    z = torch.matmul(x, y)
    print(f'GPU tensor operations: OK')
    print(f'Result shape: {z.shape}')
else:
    print('ERROR: CUDA not available for testing')
" 2>&1)

echo "$COMPUTE_TEST"
echo ""

if echo "$COMPUTE_TEST" | grep -q "Compute capability: 10.0"; then
    print_success "RTX 5070 Blackwell architecture (10.0) detected!"
elif echo "$COMPUTE_TEST" | grep -q "Compute capability:"; then
    COMPUTE_CAP=$(echo "$COMPUTE_TEST" | grep "Compute capability:" | cut -d: -f2 | xargs)
    print_warning "Compute capability: $COMPUTE_CAP (expected 10.0 for RTX 5070)"
else
    print_error "Could not determine compute capability"
fi

if echo "$COMPUTE_TEST" | grep -q "GPU tensor operations: OK"; then
    print_success "GPU tensor operations working!"
else
    print_error "GPU tensor operations failed!"
fi

echo ""

# ============================================
# 8. Service Status
# ============================================
print_status "Checking service status..."
docker compose ps
echo ""

# ============================================
# 9. Summary
# ============================================
echo "=============================================="
echo "Setup Complete!"
echo "=============================================="
echo ""
print_success "Docker images built with PyTorch nightly (CUDA 13.2)"
print_success "Services started and GPU detected"
echo ""
echo "GPU Information:"
echo "  Host GPU: $GPU_NAME"
echo "  Driver: $DRIVER_VERSION"
echo "  CUDA: $CUDA_VERSION"
echo ""
echo "Container GPU:"
echo "$GPU_TEST" | grep -E "(PyTorch|CUDA|GPU)" | sed 's/^/  /'
echo ""
echo "Next Steps:"
echo "  1. Test APIs: make test-all"
echo "  2. View logs: make logs"
echo "  3. Run FL training: See docs/RTX_5070_GPU_COMPATIBILITY_PLAN.md"
echo ""
echo "Useful Commands:"
echo "  make status          - Check service status"
echo "  make logs-node1      - View node1 logs"
echo "  make restart         - Restart services"
echo "  make down            - Stop services"
echo ""
echo "=============================================="
