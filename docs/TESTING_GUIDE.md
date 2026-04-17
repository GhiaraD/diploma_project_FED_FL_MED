# Fed-Med-FL - Ghid de Testare

## Quick Start - Test Complet în 10 Minute

### Opțiunea 1: Test Automat (Recomandat)

```bash
# 1. Pornește serviciile (dacă nu sunt pornite)
make up

# 2. Așteaptă ~30 secunde ca serviciile să pornească
sleep 30

# 3. Rulează test automat complet
make test-e2e
```

**Ce face**:
- ✅ Verifică toate serviciile
- ✅ Creează dataset-uri sintetice
- ✅ Upload datasets la toate nodurile
- ✅ Creează rundă FL
- ✅ Nodurile se înregistrează
- ✅ Training local pe toate nodurile (2 epoci)
- ✅ Agregare FedAvg
- ✅ Afișare rezultate

**Timp estimat**: 5-10 minute (depinde de hardware)

---

### Opțiunea 2: Test Manual (Pentru Debugging)

```bash
# 1. Creează dataset-uri
make create-datasets

# 2. Rulează test manual cu pași interactivi
make test-e2e-manual
```

**Avantaje**:
- Poți inspecta fiecare pas
- Useful pentru debugging
- Înveți workflow-ul FL

---

### Opțiunea 3: Test prin UI (Experiență Completă)

#### Pas 1: Pornește Serviciile

```bash
make up
```

#### Pas 2: Creează Dataset-uri

```bash
make create-datasets
```

#### Pas 3: Upload Datasets

**Node1** (http://localhost:3001):
1. Click pe **Studies** în sidebar
2. Click pe **Upload Dataset**
3. Selectează `test_dataset_node1.zip`
4. Split: `train`
5. Click **Upload**
6. **Notează dataset_id** (ex: `dataset_train_abc123`)

**Repetă pentru Node2 (3002) și Node3 (3003)**

#### Pas 4: Creează Rundă FL

```bash
curl -X POST http://localhost:8080/round/create \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "R-MANUAL-1",
    "model_name": "resnet18",
    "num_classes": 2,
    "pretrained": true,
    "hyperparameters": {
      "num_epochs": 2,
      "batch_size": 16,
      "learning_rate": 0.001,
      "optimizer": "adam"
    }
  }'
```

#### Pas 5: Join Round (pe fiecare nod)

**Node1 UI** (http://localhost:3001/federated):
1. Click pe **Federated** în sidebar
2. Introdu Round ID: `R-MANUAL-1`
3. Click **Join Round**

**Repetă pentru Node2 și Node3**

#### Pas 6: Start Training (pe fiecare nod)

**Node1 UI** (http://localhost:3001/federated):
1. Introdu Dataset ID (din Studies)
2. Click **Start Training**
3. Monitorizează progresul în stepper

**Repetă pentru Node2 și Node3**

#### Pas 7: Trigger Aggregation

```bash
# Așteaptă ca toate nodurile să termine training
# Apoi trigger aggregation
curl -X POST http://localhost:8080/round/R-MANUAL-1/aggregate
```

#### Pas 8: View Results

```bash
curl http://localhost:8080/round/R-MANUAL-1/results | python3 -m json.tool
```

---

## Verificare Rapidă (1 minut)

### Check Services

```bash
make status
```

**Output așteptat**: 10 containere running

### Test APIs

```bash
make test-all
```

**Output așteptat**:
- ✓ Central server OK
- ✓ Node1 API OK
- ✓ Node2 API OK
- ✓ Node3 API OK
- ✓ Node1 UI running
- ✓ Node2 UI running
- ✓ Node3 UI running

---

## Troubleshooting

### Serviciile nu pornesc

```bash
# Verifică logs
make logs

# Rebuild și repornește
make down
make up-build
```

### Test automat eșuează

```bash
# Verifică că serviciile rulează
make status

# Verifică logs pentru erori
make logs-central
make logs-node1

# Restart servicii
make restart
```

### Training eșuează

**Cauze posibile**:
1. **Dataset lipsă**: Verifică că dataset-ul există
   ```bash
   ls -la storage/node1/datasets/
   ```

2. **Worker nu rulează**: Verifică worker logs
   ```bash
   docker compose logs -f node1-worker
   ```

3. **Redis nu răspunde**: Restart Redis
   ```bash
   docker compose restart node1-redis
   ```

4. **Out of memory**: Reduce batch_size
   ```json
   {"batch_size": 8}  // instead of 16
   ```

### Aggregation eșuează

**Verificări**:

1. **Toate nodurile au trimis updates?**
   ```bash
   curl http://localhost:8080/round/R-1/status | python3 -m json.tool
   # Verifică: "updates_received": 3
   ```

2. **Hash-urile se potrivesc?**
   - Toate nodurile trebuie să fi plecat de la același model global

3. **Outlier detection?**
   - Dacă un delta este prea diferit, este respins
   - Verifică logs: `make logs-central`

---

## Comenzi Utile

### Logs

```bash
# Toate serviciile
make logs

# Serviciu specific
make logs-central
make logs-node1
make logs-node2
make logs-node3

# Follow logs în timp real
docker compose logs -f node1-worker
```

### Restart

```bash
# Toate serviciile
make restart

# Serviciu specific
docker compose restart node1-api
docker compose restart node1-worker
```

### Cleanup

```bash
# Oprește serviciile
make down

# Oprește și șterge volumes (ATENȚIE: șterge toate datele!)
make down-clean

# Cleanup complet
make clean
```

### Database Inspection

```bash
# Connect la SQLite database
docker compose exec node1-api sqlite3 /storage/node.db

# Queries utile:
sqlite> SELECT * FROM models;
sqlite> SELECT * FROM jobs ORDER BY created_at DESC LIMIT 5;
sqlite> SELECT * FROM datasets;
sqlite> .quit
```

---

## Metrici de Succes

### Test Automat PASS

```
✓ All services OK
✓ Datasets created and uploaded
✓ Round created
✓ All nodes joined
✓ Training completed on all nodes
✓ All updates received (3/3)
✓ Aggregation successful
✓ Results retrieved
```

### Metrici Așteptate

**După 2 epoci cu dataset-uri sintetice**:
- Accuracy: 0.70 - 0.90
- F1 Score: 0.65 - 0.88
- Loss: 0.20 - 0.50

**Note**: Valorile exacte depind de:
- Random seed
- Hardware (CPU vs GPU)
- Dataset distribution

---

## Advanced Testing

### Test cu Dataset Real

```bash
# 1. Download Kaggle Chest X-Ray dataset
# https://www.kaggle.com/datasets/paultimothymooney/chest-xray-pneumonia

# 2. Creează ZIP cu structura corectă:
#    dataset.zip
#    ├── NORMAL/
#    └── PNEUMONIA/

# 3. Upload prin UI sau API
curl -X POST http://localhost:8001/api/data/upload \
  -F "file=@real_dataset.zip" \
  -F "split=train"

# 4. Rulează FL workflow normal
```

### Test cu Mai Multe Runde

```bash
# Rundă 1
curl -X POST http://localhost:8080/round/create \
  -d '{"round_id": "R-1", ...}'
# ... training + aggregation ...

# Rundă 2 (folosește modelul agregat din R-1)
curl -X POST http://localhost:8080/round/create \
  -d '{"round_id": "R-2", ...}'
# ... training + aggregation ...

# Rundă 3, 4, 5...
```

### Performance Testing

```bash
# Test cu dataset mare
# - 1000+ imagini per nod
# - 10 epoci
# - batch_size 32

# Monitorizează:
# - Training time
# - Memory usage
# - Network traffic
# - Aggregation time
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Start services
        run: make up
      
      - name: Wait for services
        run: sleep 30
      
      - name: Run E2E test
        run: make test-e2e
      
      - name: Cleanup
        run: make down
```

---

## Resurse

### Documentație
- `IMPLEMENTATION_STATUS.md` - Status proiect
- `docs/QUICK_START.md` - Ghid pornire rapidă
- `docs/PHASE6_COMPLETE.md` - Detalii Faza 6

### Scripturi
- `scripts/automated_fl_test.py` - Test automat
- `scripts/test_e2e_fl_workflow.sh` - Test manual
- `scripts/create_test_dataset.py` - Generare datasets

### URLs
- Central: http://localhost:8080
- Node1 API: http://localhost:8001
- Node1 UI: http://localhost:3001
- Node2 API: http://localhost:8002
- Node2 UI: http://localhost:3002
- Node3 API: http://localhost:8003
- Node3 UI: http://localhost:3003

---

**Autor**: Fed-Med-FL Team  
**Versiune**: 0.1.0  
**Ultima actualizare**: 2026-04-17
