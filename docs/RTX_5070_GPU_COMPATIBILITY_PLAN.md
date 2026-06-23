# 🎮 RTX 5070 GPU Compatibility Plan

**Data**: 6 Mai 2026  
**GPU**: NVIDIA GeForce RTX 5070 (Blackwell Architecture)  
**Status**: 🔴 Incompatibil cu PyTorch actual

---

## 📊 Situația Actuală

### Hardware Detectat
```
GPU: NVIDIA GeForce RTX 5070
Driver: 596.21
CUDA: 13.2
Memory: 12GB
Compute Capability: 10.0 (Blackwell)
```

### Software Actual
```
PyTorch: >= 2.0.0 (generic, probabil 2.0-2.4)
CUDA Support: Până la 12.4
Max Compute Capability: 9.0 (RTX 40 series)
```

### 🔴 Problema
**RTX 5070 (Blackwell) necesită:**
- PyTorch 2.6+ cu suport CUDA 13.2
- Compute capability 10.0 support
- Driver 596+ (✅ AVEM)

**Proiectul actual are:**
- PyTorch 2.0+ (suportă maxim CUDA 12.4)
- Compute capability până la 9.0
- Nu recunoaște RTX 5070

---

## 🔧 Soluții Disponibile

### **Opțiunea 1: Upgrade PyTorch la 2.6+ cu CUDA 13.2** ⭐ RECOMANDAT

**Avantaje:**
- ✅ Suport nativ pentru RTX 5070
- ✅ Performance maxim (10-15x vs CPU)
- ✅ Toate features PyTorch disponibile
- ✅ Suport oficial NVIDIA

**Dezavantaje:**
- ⚠️ PyTorch 2.6 poate fi în preview/nightly
- ⚠️ Trebuie rebuild toate containerele
- ⚠️ Posibile breaking changes în API

**Pași:**
1. Update `pyproject.toml`: `torch>=2.6.0` cu CUDA 13.2
2. Rebuild Docker images
3. Test compatibilitate cu Opacus și Flower
4. Verificare training funcționează

**Timp estimat:** 1-2 ore

---

### **Opțiunea 2: Folosire CPU pentru Development** 🐌

**Avantaje:**
- ✅ Funcționează imediat (fără modificări)
- ✅ Stabil și testat
- ✅ Nu necesită rebuild

**Dezavantaje:**
- ❌ Foarte lent (10-15x mai lent decât GPU)
- ❌ Training FL va dura 30-60 minute per rundă
- ❌ Nu folosim hardware-ul disponibil

**Pași:**
1. Modifică `docker-compose.yml`: `DEVICE: cpu`
2. Comentează secțiunea `deploy.resources` (GPU)
3. Restart servicii

**Timp estimat:** 5 minute

---

### **Opțiunea 3: PyTorch Nightly Build** 🚀 EXPERIMENTAL

**Avantaje:**
- ✅ Cel mai recent suport pentru RTX 5070
- ✅ CUDA 13.2 support garantat
- ✅ Performance maxim

**Dezavantaje:**
- ⚠️ Instabil (nightly builds)
- ⚠️ Posibile bug-uri
- ⚠️ Nu recomandat pentru production

**Pași:**
1. Install PyTorch nightly cu CUDA 13.2
2. Test extensiv înainte de folosire
3. Monitorizare atentă pentru bug-uri

**Timp estimat:** 2-3 ore (cu testing)

---

### **Opțiunea 4: Downgrade CUDA Driver** ❌ NU RECOMANDAT

**Avantaje:**
- Ar putea funcționa cu PyTorch 2.4 + CUDA 12.4

**Dezavantaje:**
- ❌ RTX 5070 necesită driver 596+ (nu va funcționa cu driver vechi)
- ❌ Risc de brick GPU
- ❌ Pierdere features RTX 5070

**Status:** ❌ **NU ESTE POSIBIL** - RTX 5070 necesită driver nou

---

## 🎯 Recomandarea Mea

### Plan în 2 Faze:

#### **FAZA 1: Quick Start cu CPU** (5 minute)
Pentru a începe imediat development și testing:

```yaml
# În docker-compose.yml
environment:
  DEVICE: cpu  # Schimbă de la cuda la cpu

# Comentează:
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: 1
#           capabilities: [gpu]
```

**Beneficii:**
- Poți începe imediat să lucrezi
- Testezi funcționalitatea (chiar dacă lent)
- Verifici că totul funcționează

#### **FAZA 2: Upgrade PyTorch pentru GPU** (1-2 ore)
După ce ai verificat că totul funcționează pe CPU:

1. **Verifică disponibilitatea PyTorch 2.6+**
   ```bash
   # Check PyTorch releases
   pip index versions torch
   ```

2. **Update pyproject.toml**
   ```toml
   dependencies = [
       "torch>=2.6.0",  # Cu CUDA 13.2 support
       "torchvision>=0.21.0",  # Compatibil cu torch 2.6
       # ... rest
   ]
   ```

3. **Rebuild și Test**
   ```bash
   docker compose build --no-cache
   docker compose up -d
   
   # Test GPU detection
   docker compose exec node1-worker python -c "import torch; print(torch.cuda.is_available())"
   ```

---

## 📋 Checklist Implementare

### Faza 1: CPU Mode (Imediat)
- [ ] Modifică `docker-compose.yml` → `DEVICE: cpu`
- [ ] Comentează secțiunea GPU `deploy.resources`
- [ ] Restart servicii: `docker compose restart`
- [ ] Verifică funcționare: Test training local
- [ ] Documentează performance (baseline CPU)

### Faza 2: GPU Support (După testare CPU)
- [ ] Verifică PyTorch 2.6+ disponibil
- [ ] Update `pyproject.toml` cu torch>=2.6.0
- [ ] Update `pyproject.toml` cu torchvision compatibil
- [ ] Rebuild images: `docker compose build --no-cache`
- [ ] Test GPU detection în container
- [ ] Test training cu GPU
- [ ] Verifică Opacus compatibility
- [ ] Verifică Flower compatibility
- [ ] Benchmark performance (GPU vs CPU)
- [ ] Update documentație

---

## 🧪 Testing Plan

### Test 1: CPU Mode Verification
```bash
# Start cu CPU
docker compose up -d

# Verifică device
docker compose exec node1-worker python -c "import torch; print(f'Device: {torch.device(\"cpu\")}')"

# Run training test
curl -X POST "http://localhost:8001/api/train/local" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "test_dataset",
    "model_name": "resnet18",
    "num_epochs": 1
  }'

# Monitor timp (va fi ~5-10 min per epoch)
docker compose logs -f node1-worker
```

### Test 2: GPU Mode Verification (După upgrade)
```bash
# Rebuild cu PyTorch 2.6+
docker compose build --no-cache node1-worker

# Start services
docker compose up -d

# Verifică GPU detection
docker compose exec node1-worker python -c "
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'GPU count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    print(f'GPU name: {torch.cuda.get_device_name(0)}')
    print(f'GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB')
"

# Run training test
# Monitor timp (ar trebui ~30s-1min per epoch)
```

### Test 3: FL Training E2E
```bash
# Test complet FL cu 2 noduri
# Verifică că ambele noduri folosesc GPU (sau CPU)
# Monitorizează timp total training
```

---

## 📊 Performance Expectations

### CPU Mode (Baseline)
- **Training time**: ~5-10 minute per epoch
- **FL Round (2 epochs)**: ~20-40 minute per nod
- **Total FL (2 rounds, 2 nodes)**: ~80-160 minute

### GPU Mode (RTX 5070 - După upgrade)
- **Training time**: ~30-60 secunde per epoch
- **FL Round (2 epochs)**: ~2-4 minute per nod
- **Total FL (2 rounds, 2 nodes)**: ~8-16 minute

**Speedup așteptat: 10-15x** 🚀

---

## ⚠️ Potential Issues

### Issue 1: PyTorch 2.6 Nu Este Stable
**Soluție:** Folosește PyTorch nightly sau așteaptă release stable

### Issue 2: Opacus Incompatibility cu PyTorch 2.6
**Soluție:** 
- Verifică Opacus compatibility
- Eventual upgrade Opacus sau disable DP temporar

### Issue 3: Flower Incompatibility
**Soluție:**
- Flower ar trebui să fie agnostic de PyTorch version
- Test extensiv după upgrade

### Issue 4: CUDA Out of Memory
**Soluție:**
- Reduce batch size
- RTX 5070 are 12GB, ar trebui suficient

---

## 🔗 Resurse Utile

### PyTorch
- **Releases**: https://pytorch.org/get-started/previous-versions/
- **CUDA Compatibility**: https://pytorch.org/get-started/locally/
- **Nightly Builds**: https://pytorch.org/get-started/locally/#start-locally

### NVIDIA
- **RTX 5070 Specs**: https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/
- **CUDA Toolkit**: https://developer.nvidia.com/cuda-toolkit
- **Compute Capability**: https://developer.nvidia.com/cuda-gpus

### Compatibility Matrix
```
RTX 5070 (Blackwell) → Compute Capability 10.0
├── Requires: CUDA 13.0+
├── Requires: Driver 596+
└── Requires: PyTorch 2.6+ (cu CUDA 13.x support)
```

---

## 📞 Next Steps

### Imediat (Astăzi):
1. ✅ Documentat problema (acest fișier)
2. ⏳ Decide: CPU mode sau upgrade PyTorch?
3. ⏳ Implementează soluția aleasă
4. ⏳ Test funcționalitate

### Short-term (Săptămâna aceasta):
1. ⏳ Dacă CPU: Benchmark performance
2. ⏳ Dacă GPU: Upgrade PyTorch și test
3. ⏳ Verifică compatibility cu Opacus și Flower
4. ⏳ Documentează rezultate

### Long-term (Luna aceasta):
1. ⏳ Optimizare performance
2. ⏳ Production-ready configuration
3. ⏳ Update documentație completă

---

## ✅ Decizie Finală

**Recomand să începem cu CPU mode** pentru a verifica funcționalitatea, apoi **upgrade la PyTorch 2.6+** pentru GPU support.

**Motivație:**
- CPU mode funcționează garantat (5 minute setup)
- Poți testa FL workflow complet
- Upgrade PyTorch se face după ce știm că totul funcționează
- Risc minim, progres rapid

---

**Autor**: Fed-Med-FL Team  
**Data**: 6 Mai 2026  
**Status**: 📋 Plan Ready - Așteptăm decizie
