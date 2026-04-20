# Plan de Migrare către Flower Framework

**Data**: 2026-04-20  
**Status**: DRAFT  
**Efort estimat**: 3-5 zile  
**Complexitate**: Medie

---

## Executive Summary

Acest document descrie planul complet de migrare de la implementarea custom FL (FedAvg) către **Flower Framework** pentru proiectul Fed-Med-FL.

### Motivație

| Aspect | Custom Implementation | Flower Framework |
|--------|----------------------|------------------|
| **Linii cod FL** | ~1,200 linii | ~300 linii |
| **Protocol** | HTTP REST | gRPC (mai rapid) |
| **Securitate** | Manual (TLS, DP) | Built-in |
| **Strategies** | Doar FedAvg | FedAvg, FedProx, FedOpt, etc. |
| **Simulare** | Manual | `flwr.simulation` |
| **Monitoring** | Custom logs | Flower Dashboard |
| **Maintenance** | Custom debugging | Community support |

### Beneficii Migrare

✅ **Reducere cod**: -75% linii cod FL  
✅ **Performance**: gRPC mai rapid decât HTTP REST  
✅ **Securitate**: TLS și DP built-in  
✅ **Extensibilitate**: Acces la multiple strategies  
✅ **Testing**: Flower simulation pentru teste rapide  
✅ **Community**: Suport activ și documentație  

---

## Analiza Impactului

### Fișiere de Șters (3 fișiere, ~1,200 linii)

```
shared/python/node_core/node_core/
├── fl_client.py              ❌ ȘTERS (~350 linii)
├── fl_aggregator.py          ❌ ȘTERS (~450 linii)
└── fl_utils.py               ❌ ȘTERS (~300 linii)
```

**Justificare**: Flower înlocuiește complet aceste module cu API-ul său.

---

### Fișiere Noi de Creat (4 fișiere, ~600 linii)

```
services/central/app/
└── flower_server.py          ✅ NOU (~200 linii)

services/node/worker/app/
└── flower_client.py          ✅ NOU (~250 linii)

shared/python/node_core/node_core/
└── flower_strategy.py        ✅ NOU (~100 linii)

scripts/
└── test_flower_workflow.sh   ✅ NOU (~50 linii)
```

---

### Fișiere de Modificat (12 fișiere)

#### 1. **Core Module** (`shared/python/node_core/node_core/__init__.py`)

**Modificări**:
```python
# ÎNAINTE
from .fl_client import FederatedClient
from .fl_aggregator import FedAvgAggregator
from .fl_utils import (...)

# DUPĂ
from .flower_strategy import FedMedStrategy
# FederatedClient și FedAvgAggregator NU mai sunt exportate
```

**Impact**: MEDIU  
**Linii modificate**: ~20 linii  
**Timp estimat**: 15 minute

---

#### 2. **Dependencies** (`shared/python/node_core/pyproject.toml`)

**Modificări**:
```toml
[project]
dependencies = [
    "torch>=2.0.0",
    "torchvision>=0.15.0",
    "flwr>=1.8.0",           # ← NOU
    "flwr[simulation]>=1.8.0", # ← NOU (pentru testing)
    # ... rest
]
```

**Impact**: SCĂZUT  
**Linii modificate**: 2 linii  
**Timp estimat**: 5 minute

---

#### 3. **Central Server** (`services/central/app/main.py`)

**Modificări majore**:

**ÎNAINTE** (~450 linii):
```python
from node_core import FedAvgAggregator

aggregator = FedAvgAggregator(...)

@app.post("/round/create")
def create_round(...):
    aggregator.create_round(...)

@app.post("/update/submit")
def submit_update(...):
    aggregator.collect_update(...)

@app.post("/round/{id}/aggregate")
def aggregate_round(...):
    aggregator.aggregate_round(...)
```

**DUPĂ** (~200 linii pentru management API + Flower server separat):
```python
# main.py - Management API (păstrat pentru UI)
@app.post("/round/create")
def create_round(...):
    # Trigger Flower server să înceapă rundă
    # Sau doar salvează metadata

@app.get("/round/{id}/status")
def get_status(...):
    # Query Flower server status
```

**Nou fișier** (`flower_server.py`):
```python
import flwr as fl
from node_core import FedMedStrategy

strategy = FedMedStrategy(...)
fl.server.start_server(
    server_address="0.0.0.0:8080",
    strategy=strategy,
    config=fl.server.ServerConfig(num_rounds=5)
)
```

**Impact**: MARE  
**Linii modificate**: ~300 linii  
**Timp estimat**: 4 ore

---

#### 4. **Node Worker Tasks** (`services/node/api/app/tasks.py`)

**Modificări**:

**ÎNAINTE** (~100 linii pentru FL task):
```python
@celery_app.task(name="federated_training")
def federated_training_task(...):
    client = FederatedClient(...)
    global_state, base_hash = client.pull_global_model(...)
    # Train local
    delta = client.compute_delta(...)
    client.push_update(...)
```

**DUPĂ** (~50 linii):
```python
@celery_app.task(name="federated_training")
def federated_training_task(...):
    from .flower_client import start_flower_client
    
    start_flower_client(
        server_address=settings.FLOWER_SERVER,
        node_id=settings.NODE_ID,
        dataset_path=dataset_path,
        device=settings.DEVICE
    )
```

**Impact**: MARE  
**Linii modificate**: ~100 linii  
**Timp estimat**: 2 ore

---

#### 5. **Node API Endpoints** (`services/node/api/app/main.py`)

**Modificări**:

**ÎNAINTE**:
```python
@app.post("/api/federated/join/{round_id}")
def join_round(...):
    from node_core import FederatedClient
    client = FederatedClient(...)
    client.join_round(round_id)

@app.get("/api/federated/status/{round_id}")
def get_status(...):
    from node_core import FederatedClient
    client = FederatedClient(...)
    status = client.get_round_status(round_id)
```

**DUPĂ**:
```python
@app.post("/api/federated/join/{round_id}")
def join_round(...):
    # Salvează în DB că nodul vrea să participe
    # Flower client se va conecta automat când pornește

@app.get("/api/federated/status/{round_id}")
def get_status(...):
    # Query status din DB sau de la Flower server
```

**Impact**: MEDIU  
**Linii modificate**: ~50 linii  
**Timp estimat**: 1 oră

---

#### 6. **Docker Compose** (`docker-compose.yml`)

**Modificări**:

```yaml
services:
  central:
    environment:
      - FLOWER_SERVER_ADDRESS=0.0.0.0:8080  # ← NOU
      - NUM_ROUNDS=5                         # ← NOU
      - MIN_CLIENTS=2                        # ← NOU
    ports:
      - "8080:8080"  # gRPC port pentru Flower
      - "8081:8081"  # HTTP port pentru Management API (opțional)
    command: python -m app.flower_server     # ← MODIFICAT

  node1-worker:
    environment:
      - FLOWER_SERVER=central:8080           # ← NOU (gRPC address)
      - NODE_ID=node1
```

**Impact**: MEDIU  
**Linii modificate**: ~30 linii  
**Timp estimat**: 30 minute

---

#### 7. **Central Dockerfile** (`services/central/Dockerfile`)

**Modificări**:
```dockerfile
# Adaugă Flower
RUN pip install flwr>=1.8.0 flwr[simulation]>=1.8.0

# Expune port gRPC
EXPOSE 8080
```

**Impact**: SCĂZUT  
**Linii modificate**: 3 linii  
**Timp estimat**: 10 minute

---

#### 8. **Worker Dockerfile** (`services/node/worker/Dockerfile`)

**Modificări**:
```dockerfile
# Adaugă Flower
RUN pip install flwr>=1.8.0
```

**Impact**: SCĂZUT  
**Linii modificate**: 1 linie  
**Timp estimat**: 5 minute

---

#### 9. **Tests** (`shared/python/node_core/tests/test_fl_core.py`)

**Modificări**:

**ÎNAINTE** (~250 linii):
```python
def test_fedavg_aggregation():
    aggregator = FedAvgAggregator(...)
    # Test custom implementation
```

**DUPĂ** (~100 linii):
```python
def test_flower_strategy():
    strategy = FedMedStrategy(...)
    # Test Flower strategy
    
def test_flower_simulation():
    # Use flwr.simulation pentru teste rapide
    fl.simulation.start_simulation(...)
```

**Impact**: MARE  
**Linii modificate**: ~200 linii  
**Timp estimat**: 3 ore

---

#### 10. **Examples** (`shared/python/node_core/examples/fl_simulation.py`)

**Modificări**: Rescris complet pentru Flower simulation

**Impact**: MARE  
**Linii modificate**: ~200 linii  
**Timp estimat**: 2 ore

---

#### 11. **README** (`shared/python/node_core/README.md`)

**Modificări**: Update documentație cu exemple Flower

**Impact**: MEDIU  
**Linii modificate**: ~100 linii  
**Timp estimat**: 1 oră

---

#### 12. **Makefile** (`Makefile`)

**Modificări**:
```makefile
# Adaugă comenzi pentru Flower
test-flower:
	python -m pytest tests/test_flower_*.py -v

simulate-fl:
	python examples/flower_simulation.py
```

**Impact**: SCĂZUT  
**Linii modificate**: ~10 linii  
**Timp estimat**: 15 minute

---

## Fișiere Afectate Indirect (Documentație)

Următoarele documente trebuie actualizate pentru a reflecta noua arhitectură:

1. `docs/PHASE2_COMPLETE.md` - Update FL implementation details
2. `docs/PHASE4_COMPLETE.md` - Update Central server architecture
3. `docs/QUICK_START.md` - Update FL workflow instructions
4. `docs/TESTING_GUIDE.md` - Update FL testing procedures
5. `IMPLEMENTATION_STATUS.md` - Update FL status
6. `README.md` - Update project overview

**Impact**: SCĂZUT  
**Timp estimat**: 2 ore total

---

## Plan de Implementare

### Faza 1: Pregătire (Ziua 1 - 4 ore)

#### 1.1 Setup Environment
```bash
# Install Flower
pip install flwr>=1.8.0 flwr[simulation]>=1.8.0

# Create feature branch
git checkout -b feature/flower-migration
```

#### 1.2 Backup Current Implementation
```bash
# Create backup branch
git checkout -b backup/custom-fl-implementation
git push origin backup/custom-fl-implementation

# Return to feature branch
git checkout feature/flower-migration
```

#### 1.3 Study Flower API
- Read Flower documentation
- Review Flower examples
- Understand Strategy API
- Test Flower simulation locally

---

### Faza 2: Core Implementation (Ziua 2 - 8 ore)

#### 2.1 Create Flower Strategy (2 ore)
```bash
# Create new file
touch shared/python/node_core/node_core/flower_strategy.py
```

**Implementare**:
- Extend `fl.server.strategy.FedAvg`
- Add model persistence
- Add metrics aggregation
- Add medical imaging specific logic

#### 2.2 Create Flower Server (2 ore)
```bash
# Create new file
touch services/central/app/flower_server.py
```

**Implementare**:
- Initialize Flower server
- Configure strategy
- Add gRPC server
- Add management API (optional)

#### 2.3 Create Flower Client (2 ore)
```bash
# Create new file
touch services/node/worker/app/flower_client.py
```

**Implementare**:
- Extend `fl.client.NumPyClient`
- Implement `get_parameters()`
- Implement `fit()`
- Implement `evaluate()`

#### 2.4 Update Dependencies (1 oră)
- Update `pyproject.toml`
- Update Dockerfiles
- Rebuild containers

#### 2.5 Update Core Module (1 oră)
- Modify `__init__.py`
- Remove old imports
- Add new imports
- Update exports

---

### Faza 3: Integration (Ziua 3 - 6 ore)

#### 3.1 Update Central Server (3 ore)
- Modify `services/central/app/main.py`
- Remove old FL endpoints (sau păstrează pentru backward compatibility)
- Add Flower server startup
- Update docker-compose.yml

#### 3.2 Update Node Worker (2 ore)
- Modify `services/node/api/app/tasks.py`
- Update `federated_training_task`
- Remove old FL client usage

#### 3.3 Update Node API (1 oră)
- Modify `services/node/api/app/main.py`
- Update FL endpoints
- Adapt to Flower workflow

---

### Faza 4: Testing (Ziua 4 - 6 ore)

#### 4.1 Unit Tests (2 ore)
```bash
# Create new test file
touch shared/python/node_core/tests/test_flower_strategy.py
touch shared/python/node_core/tests/test_flower_client.py
```

**Tests**:
- Test FedMedStrategy
- Test Flower client
- Test parameter conversion
- Test metrics aggregation

#### 4.2 Integration Tests (2 ore)
```bash
# Create integration test
touch scripts/test_flower_workflow.sh
```

**Tests**:
- Test Flower server startup
- Test client connection
- Test single round
- Test multiple rounds

#### 4.3 Simulation Tests (2 ore)
```bash
# Create simulation script
touch shared/python/node_core/examples/flower_simulation.py
```

**Tests**:
- Use `flwr.simulation`
- Test with 3 virtual clients
- Verify convergence
- Compare with custom implementation

---

### Faza 5: Documentation & Cleanup (Ziua 5 - 4 ore)

#### 5.1 Update Documentation (2 ore)
- Update all docs in `/docs`
- Update README files
- Add Flower migration guide
- Add troubleshooting section

#### 5.2 Cleanup (1 oră)
```bash
# Remove old FL files
git rm shared/python/node_core/node_core/fl_client.py
git rm shared/python/node_core/node_core/fl_aggregator.py
git rm shared/python/node_core/node_core/fl_utils.py

# Remove old tests
git rm shared/python/node_core/tests/test_fl_core.py
```

#### 5.3 Final Testing (1 oră)
```bash
# Full end-to-end test
make test-e2e-flower

# Performance comparison
make benchmark-flower
```

---

## Rollback Plan

În caz de probleme majore:

### Opțiunea 1: Revert to Backup Branch
```bash
git checkout backup/custom-fl-implementation
git push origin main --force
```

### Opțiunea 2: Hybrid Approach
Păstrează ambele implementări:
```python
# În config
USE_FLOWER = os.getenv("USE_FLOWER", "false").lower() == "true"

if USE_FLOWER:
    from .flower_strategy import FedMedStrategy
else:
    from .fl_aggregator import FedAvgAggregator
```

---

## Risks & Mitigation

### Risk 1: Flower Learning Curve
**Probabilitate**: MARE  
**Impact**: MEDIU  
**Mitigare**:
- Studiază documentația Flower înainte
- Testează cu Flower simulation
- Consultă Flower community

### Risk 2: Performance Regression
**Probabilitate**: SCĂZUTĂ  
**Impact**: MARE  
**Mitigare**:
- Benchmark înainte și după
- Monitorizează training time
- Compară metrici

### Risk 3: Breaking Changes în UI
**Probabilitate**: MEDIE  
**Impact**: MEDIU  
**Mitigare**:
- Păstrează API endpoints pentru UI
- Testează UI după migrare
- Backward compatibility layer

### Risk 4: Docker Build Issues
**Probabilitate**: MEDIE  
**Impact**: SCĂZUT  
**Mitigare**:
- Test local înainte de commit
- Use multi-stage builds
- Pin Flower version

---

## Success Criteria

### Funcțional
- ✅ Flower server pornește fără erori
- ✅ Clients se conectează la server
- ✅ Training round completează cu succes
- ✅ Metrici sunt agregate corect
- ✅ Model global este salvat
- ✅ UI funcționează normal

### Performance
- ✅ Training time ≤ custom implementation
- ✅ Network overhead ≤ +10%
- ✅ Memory usage ≤ custom implementation

### Code Quality
- ✅ Reducere ≥70% linii cod FL
- ✅ Toate testele trec
- ✅ Code coverage ≥80%
- ✅ No critical bugs

---

## Post-Migration Tasks

### Immediate (Săptămâna 1)
1. Monitor production logs
2. Collect performance metrics
3. Fix any critical bugs
4. Update documentation based on feedback

### Short-term (Luna 1)
1. Explore advanced Flower features:
   - FedProx strategy
   - Differential Privacy
   - Secure Aggregation
2. Optimize performance
3. Add Flower Dashboard integration

### Long-term (Luna 2-3)
1. Implement custom strategies
2. Add simulation-based testing to CI/CD
3. Contribute improvements back to Flower
4. Write blog post about migration experience

---

## Resources

### Flower Documentation
- [Flower Docs](https://flower.dev/docs/)
- [Flower GitHub](https://github.com/adap/flower)
- [Flower Examples](https://github.com/adap/flower/tree/main/examples)

### Internal Resources
- Custom FL implementation: `shared/python/node_core/node_core/fl_*.py`
- Current tests: `shared/python/node_core/tests/test_fl_core.py`
- Documentation: `docs/PHASE2_COMPLETE.md`, `docs/PHASE4_COMPLETE.md`

### Support
- Flower Slack: [Join](https://flower.dev/join-slack)
- Flower Discuss: [Forum](https://discuss.flower.dev/)
- Team lead: [Contact info]

---

## Summary

### Effort Breakdown

| Fază | Timp | Complexitate |
|------|------|--------------|
| Pregătire | 4 ore | Scăzută |
| Core Implementation | 8 ore | Mare |
| Integration | 6 ore | Mare |
| Testing | 6 ore | Medie |
| Documentation | 4 ore | Scăzută |
| **TOTAL** | **28 ore** | **3.5 zile** |

### Files Summary

| Categorie | Count | Linii |
|-----------|-------|-------|
| Fișiere șterse | 3 | -1,200 |
| Fișiere noi | 4 | +600 |
| Fișiere modificate | 12 | ~800 |
| Documentație | 6 | ~300 |
| **NET CHANGE** | **25** | **-500** |

### Recommendation

**Recomandare**: ✅ **PROCEED cu migrarea**

**Justificare**:
1. Reducere semnificativă cod (-500 linii)
2. Acces la features avansate (DP, FedProx)
3. Community support și maintenance
4. Efort rezonabil (3.5 zile)
5. Rollback plan clar

**Când să migrezi**:
- ✅ După finalizarea features curente
- ✅ Când ai 1 săptămână buffer pentru testing
- ✅ Când echipa e disponibilă pentru support

**Când să NU migrezi**:
- ❌ În mijlocul unui sprint
- ❌ Înainte de un demo important
- ❌ Când echipa e în vacanță

---

**Autor**: Fed-Med-FL Team  
**Versiune**: 1.0  
**Status**: DRAFT - Pending Review  
**Next Review**: [Date]
