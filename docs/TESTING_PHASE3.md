# Testare Faza 3 - Node API + Worker

## Obiectiv
Verificarea funcționalității complete a Node API și Worker înainte de a trece la Faza 4.

## Componente de Testat

### 1. Node API (FastAPI)
- ✅ Health check endpoints
- ✅ Dataset management (upload, list)
- ✅ Model registry (list, promote, get info)
- ✅ Training endpoints (start, status)
- ✅ Inference endpoints (run, results)
- ✅ Federated learning endpoints (join, train, status)

### 2. Worker (Celery)
- ✅ Local training task
- ✅ Inference task with Grad-CAM
- ✅ Federated training task

### 3. Database (SQLAlchemy + SQLite)
- ✅ Models table
- ✅ Jobs table
- ✅ Datasets table
- ✅ InferenceResults table

### 4. Integration
- ✅ API → Worker communication via Celery
- ✅ Worker → Database updates
- ✅ File storage (datasets, models, results)

---

## Scenarii de Testare

### Scenariu 1: Test Basic (fără dataset real)

**Obiectiv**: Verifică că serviciile pornesc și endpoint-urile răspund.

```bash
# Pornește serviciile pentru node1
docker compose up -d node1-api node1-worker node1-redis

# Rulează testul basic
./scripts/test_node_api.sh node1
```

**Rezultate așteptate**:
- ✅ Health check: 200 OK
- ✅ Node status: returnează statistici
- ✅ List datasets: returnează array gol
- ✅ List models: returnează array gol
- ⚠️ Training/Inference: fail cu erori așteptate (no dataset/model)

---

### Scenariu 2: Test Workflow Complet (cu dataset de test)

**Obiectiv**: Testează întregul workflow: upload → train → promote → infer.

```bash
# Pornește serviciile pentru node1
docker compose up -d node1-api node1-worker node1-redis

# Rulează testul complet
./scripts/test_full_workflow.sh node1
```

**Pași**:
1. **Upload dataset** (ZIP cu NORMAL/PNEUMONIA)
   - Creează dataset de test cu 10 imagini dummy
   - Upload via POST /api/data/upload
   - Verifică că dataset_id este returnat

2. **Start training**
   - POST /api/train/local cu dataset_id
   - Verifică că job_id este returnat
   - Status = "pending"

3. **Monitor training**
   - GET /api/train/status/{job_id} la fiecare 5s
   - Așteaptă status = "completed"
   - Verifică că model_id este în result

4. **List models**
   - GET /api/models/registry
   - Verifică că modelul nou apare cu type="candidate"

5. **Promote model**
   - POST /api/models/promote cu model_id
   - Verifică că type devine "deployed"

6. **Run inference**
   - POST /api/infer cu image_paths
   - Verifică că job_id este returnat

7. **Get results**
   - GET /api/infer/results/{job_id}
   - Verifică predicted_class, confidence, gradcam_path

**Rezultate așteptate**:
- ✅ Toate pașii se execută cu succes
- ✅ Training completează în ~2-5 minute (2 epochs, dataset mic)
- ✅ Model este salvat în /storage/models/candidate/
- ✅ Inference generează Grad-CAM în /storage/results/inference/
- ✅ Database conține înregistrări în toate tabelele

---

### Scenariu 3: Test Multi-Node

**Obiectiv**: Verifică că 3 noduri pot rula simultan independent.

```bash
# Pornește toate nodurile
docker compose up -d node1-api node1-worker node1-redis \
                    node2-api node2-worker node2-redis \
                    node3-api node3-worker node3-redis

# Testează fiecare nod
./scripts/test_node_api.sh node1
./scripts/test_node_api.sh node2
./scripts/test_node_api.sh node3
```

**Rezultate așteptate**:
- ✅ Toate 3 nodurile răspund independent
- ✅ Fiecare nod are propriul storage
- ✅ Fiecare nod are propria bază de date
- ✅ Nu există interferențe între noduri

---

### Scenariu 4: Test Federated Learning (necesită Central)

**Obiectiv**: Testează workflow-ul FL complet.

**Notă**: Acest test va eșua până când implementăm Central Server (Faza 4).

```bash
# Pornește central + node1
docker compose up -d central node1-api node1-worker node1-redis

# Test FL workflow
curl -X POST http://localhost:8001/api/federated/join/R-1
curl -X POST http://localhost:8001/api/federated/train/R-1?dataset_id=dataset_train_abc123
curl http://localhost:8001/api/federated/status/R-1
```

**Rezultate așteptate (după Faza 4)**:
- ✅ Join round: success
- ✅ FL training: pull model → train → compute delta → push update
- ✅ Status: returnează info despre rundă

---

## Verificări Manuale

### 1. Verifică Logs

```bash
# API logs
docker compose logs -f node1-api

# Worker logs
docker compose logs -f node1-worker

# Redis logs
docker compose logs -f node1-redis
```

**Ce să cauți**:
- ✅ API pornește pe port 8000
- ✅ Worker se conectează la Redis
- ✅ Task-urile sunt procesate
- ❌ Erori de import sau configurare

### 2. Verifică Database

```bash
# Intră în container
docker compose exec node1-api bash

# Deschide database
sqlite3 /storage/node.db

# Verifică tabele
.tables
SELECT * FROM models;
SELECT * FROM jobs;
SELECT * FROM datasets;
SELECT * FROM inference_results;
```

### 3. Verifică Storage

```bash
# Verifică structura
docker compose exec node1-api ls -la /storage/

# Verifică datasets
docker compose exec node1-api ls -la /storage/datasets/

# Verifică models
docker compose exec node1-api ls -la /storage/models/candidate/
docker compose exec node1-api ls -la /storage/models/deployed/

# Verifică results
docker compose exec node1-api ls -la /storage/results/inference/
```

---

## Probleme Cunoscute și Soluții

### Problema 1: Worker nu se conectează la Redis

**Simptom**: Worker logs arată "Connection refused"

**Soluție**:
```bash
# Verifică că Redis rulează
docker compose ps node1-redis

# Restart worker
docker compose restart node1-worker
```

### Problema 2: Training eșuează cu "CUDA out of memory"

**Simptom**: Worker logs arată "RuntimeError: CUDA out of memory"

**Soluție**:
```bash
# Setează DEVICE=cpu în docker-compose.yml
environment:
  DEVICE: cpu
```

### Problema 3: Import error pentru node_core

**Simptom**: "ModuleNotFoundError: No module named 'node_core'"

**Soluție**:
```bash
# Verifică că node_core este instalat în Dockerfile
# Rebuild containers
docker compose build node1-api node1-worker
```

### Problema 4: Database locked

**Simptom**: "database is locked"

**Soluție**:
```bash
# SQLite nu suportă multe conexiuni concurente
# Consideră upgrade la PostgreSQL pentru producție
```

---

## Metrici de Succes

### Criterii Minime (pentru a trece la Faza 4)

- ✅ **Health check**: API răspunde la /api/health
- ✅ **Dataset upload**: Poate încărca ZIP și extrage
- ✅ **Training**: Poate antrena un model local (chiar pe dataset mic)
- ✅ **Model registry**: Poate lista, promova modele
- ✅ **Inference**: Poate rula predicții + Grad-CAM
- ✅ **Database**: Toate tabelele funcționează
- ✅ **Worker**: Task-urile sunt procesate

### Criterii Opționale (nice-to-have)

- ⚠️ **FL workflow**: Funcționează cu Central (după Faza 4)
- ⚠️ **Multi-node**: 3 noduri rulează simultan
- ⚠️ **Performance**: Training < 5 min pe dataset mic
- ⚠️ **Error handling**: Mesaje de eroare clare

---

## Checklist Final

Înainte de a trece la Faza 4, verifică:

- [ ] Toate serviciile pornesc fără erori
- [ ] Health check returnează 200 OK
- [ ] Dataset upload funcționează
- [ ] Training completează cu succes
- [ ] Model este salvat în registry
- [ ] Inference generează Grad-CAM
- [ ] Database conține date corecte
- [ ] Logs nu arată erori critice
- [ ] Storage structure este corectă
- [ ] Worker procesează task-uri

---

## Următorii Pași

După ce toate testele trec:

1. **Documentează rezultatele** în acest fișier
2. **Commit changes** cu mesaj descriptiv
3. **Treci la Faza 4**: Central Orchestrator
4. **Implementează endpoints** pentru FL orchestration
5. **Testează FL workflow** end-to-end

---

## Rezultate Testare

### Data: [TO BE FILLED]

#### Test 1: Basic Endpoints
- Status: [ ] PASS / [ ] FAIL
- Note: 

#### Test 2: Full Workflow
- Status: [ ] PASS / [ ] FAIL
- Training time: 
- Model accuracy:
- Note:

#### Test 3: Multi-Node
- Status: [ ] PASS / [ ] FAIL
- Note:

#### Probleme Întâlnite
1. 
2. 
3. 

#### Soluții Aplicate
1. 
2. 
3. 

---

**Status Final**: [ ] READY FOR PHASE 4 / [ ] NEEDS FIXES
