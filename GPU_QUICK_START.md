# 🚀 Quick Start cu GPU

## Pentru Windows (Recomandat)

### 1. Verifică că ai GPU NVIDIA
```cmd
nvidia-smi
```

### 2. Pornește cu GPU
```cmd
start_with_gpu.bat
```

Scriptul va:
- ✅ Detecta automat GPU-ul
- ✅ Configura Docker pentru GPU
- ✅ Porni toate serviciile
- ✅ Folosi GPU pentru training (10-15x mai rapid!)

---

## Pentru Linux/WSL2

```bash
./start_with_gpu.sh
```

---

## Verificare GPU

După ce serviciile pornesc, verifică că GPU-ul e folosit:

```bash
# Verifică că PyTorch vede GPU-ul
docker compose exec node1-worker python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"

# Monitorizează GPU în timp real
watch -n 1 nvidia-smi
```

---

## Performanță

### CPU (WSL2)
- ⏱️ **~25-40 minute** per nod (5 epoci)
- 🐌 Lent pentru dataset-uri mari

### GPU (NVIDIA RTX 3060)
- ⚡ **~2.5-5 minute** per nod (5 epoci)
- 🚀 **10-15x mai rapid!**

---

## Troubleshooting

### GPU nu e detectat?

1. **Instalează NVIDIA Container Toolkit** (în WSL2):
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
```

2. **Restart Docker Desktop** (din Windows)

3. **Testează din nou**:
```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### CUDA out of memory?

Reduce batch size în hyperparameters:
```json
{
  "batch_size": 16  // în loc de 32
}
```

---

## Next Steps

După ce serviciile pornesc cu GPU:

1. **Upload datasets** (dacă nu ai făcut deja):
```bash
./scripts/upload_node_datasets.sh
```

2. **Creează rundă FL**:
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

3. **Start training** și bucură-te de viteza GPU-ului! 🎮⚡

---

**Documentație completă**: `docs/GPU_SETUP.md`
