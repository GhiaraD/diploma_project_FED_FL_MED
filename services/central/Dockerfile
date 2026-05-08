FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and PyTorch
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first
COPY shared/python/node_core /app/shared/python/node_core

# Install PyTorch with CUDA 13.2 support for RTX 5070 (Blackwell)
# Using nightly build for CUDA 13.2 compatibility
RUN pip install --no-cache-dir --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu132

# Install shared library (will skip torch/torchvision since already installed)
RUN pip install --no-cache-dir -e /app/shared/python/node_core

# Install Central dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    flwr>=1.8.0

# Copy Central code
COPY services/central/app /app/app

# Create storage directories
RUN mkdir -p /storage/models

EXPOSE 8080

CMD ["python", "-m", "app.main"]
