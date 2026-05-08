#!/bin/bash

# ============================================
# WSL Dependencies Setup for Fed-Med-FL
# ============================================
# 
# This script installs all necessary packages
# and utilities needed to run Fed-Med-FL on WSL2
#
# Date: May 6, 2026
# ============================================

set -e  # Exit on error

echo "=============================================="
echo "Fed-Med-FL - WSL Dependencies Setup"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Check if running on WSL
if ! grep -qi microsoft /proc/version; then
    print_warning "This doesn't appear to be WSL. Continuing anyway..."
fi

# Check Ubuntu version
print_status "Checking Ubuntu version..."
. /etc/os-release
echo "  OS: $PRETTY_NAME"
echo ""

# ============================================
# 1. Update Package Lists
# ============================================
print_status "Updating package lists..."
sudo apt-get update -qq
print_success "Package lists updated"
echo ""

# ============================================
# 2. Install Essential Build Tools
# ============================================
print_status "Installing essential build tools..."

ESSENTIAL_PACKAGES=(
    "build-essential"      # GCC, G++, make
    "git"                  # Version control
    "curl"                 # HTTP client
    "wget"                 # Download utility
    "ca-certificates"      # SSL certificates
    "gnupg"               # GPG keys
    "lsb-release"         # Linux Standard Base
)

for package in "${ESSENTIAL_PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii  $package "; then
        print_success "$package already installed"
    else
        print_status "Installing $package..."
        sudo apt-get install -y -qq "$package"
        print_success "$package installed"
    fi
done
echo ""

# ============================================
# 3. Install Python and Dependencies
# ============================================
print_status "Installing Python and dependencies..."

PYTHON_PACKAGES=(
    "python3"              # Python 3
    "python3-pip"          # Python package manager
    "python3-venv"         # Virtual environments
    "python3-dev"          # Python development headers
)

for package in "${PYTHON_PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii  $package "; then
        print_success "$package already installed"
    else
        print_status "Installing $package..."
        sudo apt-get install -y -qq "$package"
        print_success "$package installed"
    fi
done

# Check Python version
PYTHON_VERSION=$(python3 --version)
print_success "Python installed: $PYTHON_VERSION"
echo ""

# ============================================
# 4. Install JSON Processing Tools
# ============================================
print_status "Installing JSON processing tools..."

if command -v jq &> /dev/null; then
    print_success "jq already installed"
else
    print_status "Installing jq..."
    sudo apt-get install -y -qq jq
    print_success "jq installed"
fi
echo ""

# ============================================
# 5. Install Docker CLI (if not present)
# ============================================
print_status "Checking Docker installation..."

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_success "Docker already installed: $DOCKER_VERSION"
    
    # Check if Docker daemon is accessible
    if docker ps &> /dev/null; then
        print_success "Docker daemon is accessible"
    else
        print_warning "Docker daemon not accessible. Make sure Docker Desktop is running."
        print_warning "Enable WSL integration in Docker Desktop settings."
    fi
else
    print_warning "Docker not found. Please install Docker Desktop for Windows."
    print_warning "Download from: https://www.docker.com/products/docker-desktop"
fi
echo ""

# ============================================
# 6. Install Docker Compose (if not present)
# ============================================
print_status "Checking Docker Compose installation..."

if command -v docker compose &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version)
    print_success "Docker Compose already installed: $COMPOSE_VERSION"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    print_success "Docker Compose (standalone) installed: $COMPOSE_VERSION"
else
    print_warning "Docker Compose not found. It should come with Docker Desktop."
fi
echo ""

# ============================================
# 7. Install System Utilities
# ============================================
print_status "Installing system utilities..."

SYSTEM_PACKAGES=(
    "htop"                 # Process viewer
    "tree"                 # Directory tree viewer
    "vim"                  # Text editor
    "nano"                 # Text editor
    "zip"                  # Compression
    "unzip"                # Decompression
    "pciutils"             # lspci for GPU detection
)

for package in "${SYSTEM_PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii  $package "; then
        print_success "$package already installed"
    else
        print_status "Installing $package..."
        sudo apt-get install -y -qq "$package"
        print_success "$package installed"
    fi
done
echo ""

# ============================================
# 8. Install Python Packages (for scripts)
# ============================================
print_status "Installing Python packages for scripts..."

PYTHON_MODULES=(
    "requests"             # HTTP library
    "cryptography"         # Cryptography library
)

for module in "${PYTHON_MODULES[@]}"; do
    if python3 -c "import $module" 2>/dev/null; then
        print_success "Python module '$module' already installed"
    else
        print_status "Installing Python module '$module'..."
        pip3 install -q "$module"
        print_success "Python module '$module' installed"
    fi
done
echo ""

# ============================================
# 9. Verify NVIDIA GPU (if available)
# ============================================
print_status "Checking NVIDIA GPU..."

if command -v nvidia-smi &> /dev/null; then
    print_success "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | while read line; do
        echo "  $line"
    done
    
    # Check CUDA version
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}')
    print_success "CUDA Version: $CUDA_VERSION"
else
    print_warning "nvidia-smi not found. GPU support may not be available."
    print_warning "For GPU support, ensure NVIDIA drivers are installed on Windows."
fi
echo ""

# ============================================
# 10. Create Project Directories (if needed)
# ============================================
print_status "Checking project directories..."

REQUIRED_DIRS=(
    "storage/central"
    "storage/node1"
    "storage/node2"
    "storage/node3"
    "certificates"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        print_success "Directory exists: $dir"
    else
        print_status "Creating directory: $dir"
        mkdir -p "$dir"
        print_success "Directory created: $dir"
    fi
done
echo ""

# ============================================
# 11. Set Permissions for Scripts
# ============================================
print_status "Setting executable permissions for scripts..."

if [ -d "scripts" ]; then
    chmod +x scripts/*.sh 2>/dev/null || true
    print_success "Script permissions set"
else
    print_warning "Scripts directory not found"
fi
echo ""

# ============================================
# 12. Verification Summary
# ============================================
echo "=============================================="
echo "Installation Summary"
echo "=============================================="
echo ""

# Check all critical tools
TOOLS=(
    "python3:Python 3"
    "pip3:pip"
    "docker:Docker"
    "git:Git"
    "curl:curl"
    "jq:jq"
    "make:make"
)

ALL_OK=true

for tool_info in "${TOOLS[@]}"; do
    IFS=':' read -r cmd name <<< "$tool_info"
    if command -v "$cmd" &> /dev/null; then
        version=$($cmd --version 2>&1 | head -1)
        print_success "$name: ✓ ($version)"
    else
        print_error "$name: ✗ NOT FOUND"
        ALL_OK=false
    fi
done

echo ""

# Docker daemon check
if docker ps &> /dev/null; then
    print_success "Docker daemon: ✓ ACCESSIBLE"
else
    print_warning "Docker daemon: ⚠ NOT ACCESSIBLE"
    print_warning "  → Start Docker Desktop on Windows"
    print_warning "  → Enable WSL integration in Docker Desktop settings"
    ALL_OK=false
fi

echo ""

# GPU check
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    print_success "GPU: ✓ $GPU_NAME"
else
    print_warning "GPU: ⚠ NOT DETECTED (CPU mode will be used)"
fi

echo ""
echo "=============================================="

if [ "$ALL_OK" = true ]; then
    print_success "All dependencies installed successfully!"
    echo ""
    print_status "Next steps:"
    echo "  1. Make sure Docker Desktop is running"
    echo "  2. Run: make up-cpu (for CPU mode)"
    echo "  3. Or follow RTX_5070_GPU_COMPATIBILITY_PLAN.md for GPU setup"
else
    print_warning "Some dependencies are missing or not accessible."
    print_warning "Please review the errors above and fix them."
fi

echo ""
echo "=============================================="
echo "Setup Complete!"
echo "=============================================="
