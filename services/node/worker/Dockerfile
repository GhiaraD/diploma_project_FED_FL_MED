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

# Install worker dependencies
RUN pip install --no-cache-dir \
    celery==5.3.4 \
    redis==5.0.1 \
    sqlalchemy==2.0.23 \
    flwr>=1.8.0

# Copy worker and API code (worker needs API for tasks)
COPY services/node/worker/app /app/worker
COPY services/node/api/app /app/api

# Set Python path
ENV PYTHONPATH=/app:/app/shared/python/node_core

WORKDIR /app/worker

CMD ["celery", "-A", "run_worker:celery_app", "worker", "--loglevel=INFO", "--max-tasks-per-child=1"]
