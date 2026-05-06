# Fix: Make Opacus Installation Permanent

**Problema**: Opacus a fost instalat manual cu `pip install` și va dispărea la rebuild.

**Soluție**: Actualizează Dockerfile să instaleze dependencies din `pyproject.toml` corect.

---

## 🔍 Root Cause

Dockerfile-ul pentru worker nu instalează corect `node-core` cu toate dependencies din `pyproject.toml`.

---

## 🔧 Solution

### Option 1: Force Reinstall în Dockerfile (Recomandat)

**Fișier**: `services/node/worker/Dockerfile`

Adaugă după instalarea `node-core`:

```dockerfile
# Install node-core package
COPY --from=node-core-builder /workspace/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl

# ADAUGĂ AICI: Force install DP dependencies
RUN pip install --no-cache-dir opacus>=1.4.0 dp-accounting>=0.4.0
```

### Option 2: Fix pyproject.toml Installation

Verifică că în Dockerfile se instalează corect din `pyproject.toml`:

```dockerfile
# În loc de:
RUN pip install --no-cache-dir /tmp/*.whl

# Folosește:
RUN pip install --no-cache-dir /tmp/*.whl && \
    pip install --no-cache-dir opacus>=1.4.0 dp-accounting>=0.4.0
```

### Option 3: Separate Requirements File

Creează `services/node/worker/requirements-dp.txt`:

```txt
opacus>=1.4.0
dp-accounting>=0.4.0
```

În Dockerfile:

```dockerfile
COPY requirements-dp.txt .
RUN pip install --no-cache-dir -r requirements-dp.txt
```

---

## 🚀 Apply Fix

### Step 1: Update Dockerfile
```bash
# Edit Dockerfile
nano services/node/worker/Dockerfile

# Add line:
RUN pip install --no-cache-dir opacus>=1.4.0 dp-accounting>=0.4.0
```

### Step 2: Rebuild
```bash
docker compose build node1-worker node2-worker node3-worker
```

### Step 3: Restart
```bash
docker compose up -d node1-worker node2-worker node3-worker
```

### Step 4: Verify
```bash
docker compose exec node1-worker python -c "import opacus; print(f'✅ Opacus {opacus.__version__}')"
```

---

## ✅ Verification

După rebuild, verifică că Opacus este instalat permanent:

```bash
# Stop containers
docker compose down

# Start containers (fără manual install)
docker compose up -d

# Wait for startup
sleep 10

# Verify Opacus
docker compose exec node1-worker python -c "import opacus; print(f'✅ Opacus {opacus.__version__}')"
docker compose exec node2-worker python -c "import opacus; print(f'✅ Opacus {opacus.__version__}')"
docker compose exec node3-worker python -c "import opacus; print(f'✅ Opacus {opacus.__version__}')"
```

Dacă toate printează `✅ Opacus 1.5.4` (sau mai nou), fix-ul a funcționat!

---

## 📝 Current Workaround

Până când Dockerfile-ul este fixat, folosește acest script pentru a instala Opacus după fiecare restart:

```bash
#!/bin/bash
# install_opacus.sh

echo "Installing Opacus on all nodes..."

docker compose exec -T node1-worker pip install -q opacus dp-accounting
docker compose exec -T node2-worker pip install -q opacus dp-accounting
docker compose exec -T node3-worker pip install -q opacus dp-accounting

echo "✅ Opacus installed on all nodes"

# Verify
docker compose exec -T node1-worker python -c "import opacus; print(f'Node1: Opacus {opacus.__version__}')"
docker compose exec -T node2-worker python -c "import opacus; print(f'Node2: Opacus {opacus.__version__}')"
docker compose exec -T node3-worker python -c "import opacus; print(f'Node3: Opacus {opacus.__version__}')"
```

Salvează ca `install_opacus.sh` și rulează după fiecare `docker compose up`:

```bash
chmod +x install_opacus.sh
./install_opacus.sh
```

---

**Status**: 🔄 Workaround aplicat, fix permanent planificat
