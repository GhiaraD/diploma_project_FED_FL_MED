#!/bin/bash
# Setup script for node_core shared library

set -e

echo "=========================================="
echo "Setting up node_core shared library"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Navigate to node_core directory
cd "$(dirname "$0")/../shared/python/node_core"

echo -e "\n${YELLOW}📦 Installing node_core in editable mode...${NC}"
pip install -e .

echo -e "\n${YELLOW}📦 Installing development dependencies...${NC}"
pip install -e ".[dev]"

echo -e "\n${GREEN}✅ node_core installed successfully!${NC}"

# Run tests if pytest is available
if command -v pytest &> /dev/null; then
    echo -e "\n${YELLOW}🧪 Running tests...${NC}"
    pytest tests/ -v
    echo -e "\n${GREEN}✅ All tests passed!${NC}"
else
    echo -e "\n${YELLOW}⚠️  pytest not found, skipping tests${NC}"
fi

echo -e "\n${GREEN}=========================================="
echo "Setup complete!"
echo "==========================================${NC}"
echo ""
echo "You can now import node_core in your Python code:"
echo "  from node_core import get_model, train_model, GradCAM"
echo ""
echo "Run examples:"
echo "  python examples/train_example.py"
echo "  python examples/inference_example.py"
echo ""
