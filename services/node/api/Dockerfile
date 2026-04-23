FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV, PyTorch, and Docker CLI
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    ca-certificates \
    curl \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first
COPY shared/python/node_core /app/shared/python/node_core

# Install shared library
RUN pip install --no-cache-dir -e /app/shared/python/node_core

# Install API dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    sqlalchemy==2.0.23 \
    celery==5.3.4 \
    redis==5.0.1 \
    python-multipart==0.0.6

# Copy API code
COPY services/node/api/app /app/app

# Copy Flower client for federated training tasks
COPY services/node/worker/app/flower_client.py /app/app/flower_client.py

# Create storage directories
RUN mkdir -p /storage/datasets /storage/models/candidate /storage/models/deployed /storage/models/archived /storage/results/inference /storage/results/training /storage/deltas

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
