# GPU Setup Guide for Fed-Med-FL

## Prerequisites

### Hardware
- NVIDIA GPU with CUDA support (GTX 1060 or newer recommended)
- Minimum 6GB VRAM for ResNet18 training

### Software
- Windows 10/11 with WSL2
- Docker Desktop for Windows (latest version)
- NVIDIA GPU drivers (latest)

---

## Setup Steps

### 1. Install NVIDIA GPU Drivers

Download and install the latest NVIDIA drivers for your GPU:
- https://www.nvidia.com/Download/index.aspx

Verify installation:
```cmd
nvidia-smi
```

You should see your GPU listed with driver version.

---

### 2. Install Docker Desktop with WSL2

1. Download Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Install with WSL2 backend enabled
3. In Docker Desktop settings:
   - Go to **Settings → General**
   - Enable "Use the WSL 2 based engine"
   - Go to **Settings → Resources → WSL Integration**
   - Enable integration with your WSL2 distro (Ubuntu)

---

### 3. Install NVIDIA Container Toolkit (in WSL2)

Open WSL2 terminal and run:

```bash
# Add NVIDIA package repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install nvidia-docker2
sudo apt-get update
sudo apt-get install -y nvidia-docker2

# Restart Docker (from Windows)
# Close and reopen Docker Desktop
```

---

### 4. Verify GPU Support in Docker

In WSL2 terminal:

```bash
# Test NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

You should see your GPU information displayed.

---

## Running Fed-Med-FL with GPU

### Option 1: Windows Batch Script (Recommended)

From Windows Command Prompt or PowerShell:

```cmd
cd path\to\diploma_project_FED_FL_MED
start_with_gpu.bat
```

The script will:
- ✅ Check if GPU is available
- ✅ Automatically use GPU if detected
- ✅ Fall back to CPU if GPU not available
- ✅ Start all services

---

### Option 2: WSL2 Bash Script

From WSL2 terminal:

```bash
cd /home/student/disertatie/diploma_project_FED_FL_MED
./start_with_gpu.sh
```

---

### Option 3: Manual Docker Compose

```bash
# With GPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

# Without GPU (CPU only)
docker compose up -d
```

---

## Verify GPU Usage

### Check if containers see GPU

```bash
# Check node1-worker
docker compose exec node1-worker nvidia-smi

# Check if PyTorch sees GPU
docker compose exec node1-worker python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
```

Expected output:
```
CUDA available: True
GPU: NVIDIA GeForce RTX 3060
```

---

### Monitor GPU usage during training

**Windows Task Manager:**
- Open Task Manager (Ctrl+Shift+Esc)
- Go to "Performance" tab
- Select "GPU" to see usage

**nvidia-smi in real-time:**
```bash
watch -n 1 nvidia-smi
```

---

## Performance Comparison

### CPU Training (WSL2)
- **Time per epoch**: ~5-8 minutes
- **Total training (5 epochs)**: ~25-40 minutes per node
- **Memory**: ~4-8 GB RAM

### GPU Training (NVIDIA RTX 3060)
- **Time per epoch**: ~30-60 seconds
- **Total training (5 epochs)**: ~2.5-5 minutes per node
- **Memory**: ~2-4 GB VRAM

**Speedup: ~10-15x faster with GPU!**

---

## Troubleshooting

### GPU not detected in Docker

**Check Docker Desktop settings:**
1. Open Docker Desktop
2. Settings → Resources → WSL Integration
3. Ensure your distro is enabled
4. Restart Docker Desktop

**Check NVIDIA runtime:**
```bash
docker info | grep -i runtime
```

Should show `nvidia` in the list.

---

### "nvidia-smi: command not found" in container

The base Python image doesn't include NVIDIA tools. This is normal.

To verify GPU access:
```bash
docker compose exec node1-worker python3 -c "import torch; print(torch.cuda.is_available())"
```

---

### CUDA out of memory

**Reduce batch size** in training:

Edit hyperparameters when creating FL round:
```json
{
  "batch_size": 16,  // Reduce from 32
  "num_epochs": 5
}
```

Or set environment variable:
```yaml
# docker-compose.gpu.yml
environment:
  - DEFAULT_BATCH_SIZE=16
```

---

### Training still slow with GPU

**Check GPU utilization:**
```bash
nvidia-smi
```

If GPU usage is low (<50%):
- Increase batch size (if VRAM allows)
- Check if data loading is bottleneck (increase num_workers)
- Verify DEVICE=cuda is set

---

## Batch Size Recommendations by GPU

| GPU Model | VRAM | Recommended Batch Size |
|-----------|------|------------------------|
| GTX 1060 | 6GB | 16 |
| RTX 2060 | 6GB | 16-24 |
| RTX 3060 | 12GB | 32-48 |
| RTX 3080 | 10GB | 32-48 |
| RTX 4090 | 24GB | 64-128 |

---

## Next Steps

After GPU setup:

1. **Start services with GPU:**
   ```cmd
   start_with_gpu.bat
   ```

2. **Upload datasets** (if not already done):
   ```bash
   ./scripts/upload_node_datasets.sh
   ```

3. **Create FL round** with appropriate batch size:
   ```bash
   curl -X POST http://localhost:8080/round/create \
     -H 'Content-Type: application/json' \
     -d '{
       "round_id": "R-GPU-1",
       "model_name": "resnet18",
       "num_classes": 2,
       "pretrained": true,
       "hyperparameters": {
         "num_epochs": 5,
         "batch_size": 32,
         "learning_rate": 0.001,
         "optimizer": "adam"
       }
     }'
   ```

4. **Start training** and enjoy 10x speedup! 🚀

---

## Resources

- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- [Docker GPU Support](https://docs.docker.com/config/containers/resource_constraints/#gpu)
- [WSL2 GPU Support](https://docs.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute)
- [PyTorch CUDA](https://pytorch.org/get-started/locally/)

---

**Status**: Ready for GPU-accelerated Federated Learning! 🎮⚡
