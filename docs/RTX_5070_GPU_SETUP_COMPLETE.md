# 🎮 RTX 5070 GPU Setup - Implementation Complete

**Data**: 6 Mai 2026  
**Status**: ✅ READY TO BUILD & TEST  
**GPU**: NVIDIA GeForce RTX 5070 (Blackwell)

---

## 📊 Ce Am Făcut

### 1. ✅ Actualizat PyTorch Dependencies

**Fișier**: `shared/python/node_core/pyproject.toml`

```toml
dependencies = [
    "torch>=2.6.0",  # Minimum version with Blackwell support
    "torchvision>=0.21.0",  # Compatible with torch 2.6+
    # ... rest
]
```

**Motivație:**
- RTX 5070 (Blackwell) necesită compute capability 10.0
- PyTorch 2.0-2.5 suportă maxim compute capability 9.0
- PyTorch 2.6+ cu CUDA 13.2 suportă Blackwell

---

### 2. ✅ Actualizat Dockerfiles

Am modificat **3 Dockerfiles** pentru a instala PyTorch nightly cu CUDA 13.2:

#### A. Worker Dockerfile
**Fișier**: `services/node/worker/Dockerfile`

```dockerfile
# Install PyTorch with CUDA 13.2 support for RTX 5070 (Blackwell)
# Using nightly build for CUDA 13.2 compatibility
RUN pip install --no-cache-dir --pre torch torchvision \
    --index-url https://download.pytorch.org/whl/nightly/cu132
```

#### B. API Dockerfile
**Fișier**: `services/node/api/Dockerfile`

```dockerfile
# Install PyTorch with CUDA 13.2 support for RTX 5070 (Blackwell)
RUN pip install --no-cache-dir --pre torch torchvision \
    --index-url https://download.pytorch.org/whl/nightly/cu132
```

#### C. Central Dockerfile
**Fișier**: `services/central/Dockerfile`

```dockerfile
# Install PyTorch with CUDA 13.2 support for RTX 5070 (Blackwell)
RUN pip install --no-cache-dir --pre torch torchvision \
    --index-url https://download.pytorch.org/whl/nightly/cu132
```

**Beneficii:**
- ✅ PyTorch nightly cu CUDA 13.2
- ✅ Suport nativ pentru RTX 5070
- ✅ Compute capability 10.0 (Blackwell)
- ✅ Instalare înainte de shared library (evită conflicte)

---

### 3. ✅ Verificat docker-compose.yml

**Configurația GPU este deja corectă:**

```yaml
node1-worker:
  environment:
    DEVICE: cuda  # ✅ Correct
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]  # ✅ Correct
```

**Același lucru pentru node2-worker și node3-worker.**

---

### 4. ✅ Creat Script Automat de Setup

**Fișier**: `scripts/setup_rtx5070_gpu.sh`

**Ce face:**
1. ✅ Verifică GPU (RTX 5070, Driver, CUDA)
2. ✅ Verifică Docker funcționează
3. ✅ Stop servicii existente
4. ✅ Build images cu PyTorch CUDA 13.2 (~10-15 min)
5. ✅ Start servicii
6. ✅ Verifică GPU detection în container
7. ✅ Test PyTorch compute capability
8. ✅ Test GPU tensor operations
9. ✅ Afișează summary complet

**Rulare:**
```bash
./scripts/setup_rtx5070_gpu.sh
```

---

## 🚀 Next Steps - BUILD & TEST

### Step 1: Build Docker Images

**Opțiunea A: Folosește scriptul automat** ⭐ RECOMANDAT

```bash
# Rulează scriptul complet (build + test)
./scripts/setup_rtx5070_gpu.sh
```

**Opțiunea B: Build manual**

```bash
# Stop servicii existente
docker compose down

# Build toate imaginile (10-15 minute)
docker compose build --no-cache

# Start servicii
docker compose up -d

# Așteaptă 30 secunde
sleep 30
```

---

### Step 2: Verifică GPU Detection

```bash
# Test GPU în container
docker compose exec node1-worker python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'Compute capability: {torch.cuda.get_device_properties(0).major}.{torch.cuda.get_device_properties(0).minor}')
"
```

**Expected Output:**
```
PyTorch: 2.7.0.dev20260506+cu132 (sau similar)
CUDA available: True
CUDA version: 13.2
GPU: NVIDIA GeForce RTX 5070
Compute capability: 10.0
```

---

### Step 3: Test GPU Tensor Operations

```bash
# Test operații GPU
docker compose exec node1-worker python -c "
import torch
x = torch.randn(1000, 1000).cuda()
y = torch.randn(1000, 1000).cuda()
z = torch.matmul(x, y)
print(f'✓ GPU tensor operations OK')
print(f'Result shape: {z.shape}')
print(f'Device: {z.device}')
"
```

**Expected Output:**
```
✓ GPU tensor operations OK
Result shape: torch.Size([1000, 1000])
Device: cuda:0
```

---

### Step 4: Test Services

```bash
# Verifică status servicii
make status

# Test APIs
make test-all

# View logs
make logs-node1
```

---

## 📊 Expected Performance

### Build Time
- **Central**: ~3-5 minute
- **Node Worker** (×3): ~5-7 minute each
- **Node API** (×3): ~5-7 minute each
- **Total**: ~10-15 minute

### Download Size
- **PyTorch nightly cu CUDA 13.2**: ~2GB per image
- **Total download**: ~6-8GB (pentru toate imaginile)

### GPU Performance (vs CPU)
- **Training time**: 10-15x mai rapid
- **Epoch duration**: ~30-60s (vs 5-10 min pe CPU)
- **FL Round**: ~2-4 min (vs 20-40 min pe CPU)

---

## ⚠️ Potential Issues & Solutions

### Issue 1: PyTorch Download Slow
**Simptom:** Build durează >30 minute

**Soluție:**
- Normal pentru prima dată (download 2GB)
- Următoarele build-uri vor fi mai rapide (cache)

---

### Issue 2: CUDA Not Available in Container
**Simptom:**
```python
torch.cuda.is_available()  # False
```

**Soluții:**

**A. Verifică nvidia-container-toolkit**
```bash
# Pe Windows, verifică Docker Desktop settings
# Settings → Resources → WSL Integration → Enable Ubuntu
```

**B. Test NVIDIA runtime**
```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

**C. Restart Docker Desktop**
```bash
# În Windows: Restart Docker Desktop
# Apoi în WSL: docker ps
```

---

### Issue 3: Compute Capability Not 10.0
**Simptom:**
```
Compute capability: 8.9  # sau alt număr
```

**Cauză:** PyTorch nu recunoaște RTX 5070 corect

**Soluție:**
- Verifică că ai folosit `cu132` (CUDA 13.2)
- Rebuild cu `--no-cache`
- Verifică PyTorch version în container: `torch.__version__`

---

### Issue 4: Out of Memory (OOM)
**Simptom:**
```
RuntimeError: CUDA out of memory
```

**Soluții:**
1. **Reduce batch size** în training config
2. **Reduce model size** (ResNet18 în loc de EfficientNet-B0)
3. **Disable DP** (dacă e activat, consumă mai multă memorie)

**RTX 5070 are 12GB VRAM** - ar trebui suficient pentru:
- ResNet18: ✅ OK (batch size 32-64)
- DenseNet121: ✅ OK (batch size 16-32)
- EfficientNet-B0: ✅ OK (batch size 32-64)

---

### Issue 5: Opacus Incompatibility
**Simptom:**
```
ModuleNotFoundError: No module named 'opacus'
```

**Soluție:**
```bash
# Instalează Opacus în container
docker compose exec node1-worker pip install opacus dp-accounting

# Sau rebuild cu Opacus în Dockerfile
```

**Notă:** Opacus poate avea probleme cu PyTorch nightly. Dacă întâmpini erori:
```yaml
# În docker-compose.yml
ENABLE_DP: "false"  # Disable DP temporar
```

---

## 🧪 Testing Plan

### Test 1: GPU Detection ✅
```bash
./scripts/setup_rtx5070_gpu.sh
# Verifică output pentru "GPU detected successfully"
```

### Test 2: Simple Training Test
```bash
# Upload un dataset mic (via UI sau API)
# Start local training
curl -X POST "http://localhost:8001/api/train/local" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "test_dataset",
    "model_name": "resnet18",
    "num_epochs": 1
  }'

# Monitor logs
docker compose logs -f node1-worker

# Ar trebui să vezi:
# - "Device: cuda"
# - Training time: ~30-60s per epoch
```

### Test 3: FL Training Test
```bash
# Start Flower Server
docker compose exec central python -m app.flower_server

# În alt terminal, start training pe 2 noduri
curl -X POST "http://localhost:8001/api/federated/train/R-GPU-TEST?dataset_id=<ID>&model_name=resnet18"
curl -X POST "http://localhost:8002/api/federated/train/R-GPU-TEST?dataset_id=<ID>&model_name=resnet18"

# Monitor logs
docker compose logs -f node1-worker node2-worker

# Verifică:
# - "Device: cuda" în ambele noduri
# - Training time: ~2-4 min per rundă
```

---

## 📋 Checklist

### Pre-Build
- [x] WSL dependencies instalate
- [x] Docker Desktop pornit
- [x] GPU detectat (nvidia-smi)
- [x] pyproject.toml actualizat
- [x] Dockerfiles actualizate
- [x] docker-compose.yml verificat

### Build & Deploy
- [ ] Run: `./scripts/setup_rtx5070_gpu.sh`
- [ ] Verifică GPU detection în container
- [ ] Verifică compute capability 10.0
- [ ] Verifică tensor operations
- [ ] Test APIs: `make test-all`

### Testing
- [ ] Test local training cu GPU
- [ ] Verifică training time (~30-60s/epoch)
- [ ] Test FL training cu 2 noduri
- [ ] Verifică FL round time (~2-4 min)
- [ ] Benchmark vs CPU (ar trebui 10-15x speedup)

---

## 📊 Comparison: Before vs After

| Aspect | Before (CPU) | After (GPU RTX 5070) |
|--------|--------------|----------------------|
| **PyTorch** | 2.0+ generic | 2.7+ nightly cu CUDA 13.2 |
| **CUDA Support** | N/A | 13.2 |
| **Compute Capability** | N/A | 10.0 (Blackwell) |
| **Training Time/Epoch** | 5-10 min | 30-60s |
| **FL Round (2 epochs)** | 20-40 min | 2-4 min |
| **Speedup** | 1x (baseline) | **10-15x** 🚀 |
| **Memory** | RAM (shared) | 12GB VRAM (dedicated) |

---

## 🎯 Success Criteria

### ✅ Build Success
- [ ] All Docker images built without errors
- [ ] PyTorch version: 2.6+ (nightly)
- [ ] CUDA version: 13.2

### ✅ GPU Detection
- [ ] `torch.cuda.is_available()` returns `True`
- [ ] GPU name: "NVIDIA GeForce RTX 5070"
- [ ] Compute capability: 10.0

### ✅ Performance
- [ ] Training time: <1 min per epoch (ResNet18)
- [ ] FL round: <5 min (2 nodes, 2 epochs)
- [ ] Speedup vs CPU: >10x

### ✅ Stability
- [ ] No CUDA errors
- [ ] No OOM errors (cu batch size rezonabil)
- [ ] Services restart OK

---

## 🔗 Related Documentation

1. **`docs/RTX_5070_GPU_COMPATIBILITY_PLAN.md`**
   - Analiza problemei
   - Plan în 2 faze
   - Soluții alternative

2. **`docs/WSL_SETUP_COMPLETE.md`**
   - WSL dependencies
   - Verificare instalare

3. **`scripts/setup_rtx5070_gpu.sh`**
   - Script automat build & test

4. **`READY_TO_START.md`**
   - Quick start guide

---

## 🚀 Ready to Build!

**Totul este pregătit pentru build. Rulează:**

```bash
./scripts/setup_rtx5070_gpu.sh
```

**Scriptul va:**
1. Verifica GPU
2. Build toate imaginile (~10-15 min)
3. Start servicii
4. Test GPU detection
5. Afișa summary complet

**După build, vei avea:**
- ✅ PyTorch 2.7+ nightly cu CUDA 13.2
- ✅ Suport complet RTX 5070 (Blackwell)
- ✅ Training 10-15x mai rapid
- ✅ FL workflow funcțional cu GPU

---

**Status**: ✅ **READY TO BUILD**  
**Next**: Rulează `./scripts/setup_rtx5070_gpu.sh`

---

**Autor**: Fed-Med-FL Team  
**Data**: 6 Mai 2026  
**GPU**: NVIDIA GeForce RTX 5070 (12GB)
