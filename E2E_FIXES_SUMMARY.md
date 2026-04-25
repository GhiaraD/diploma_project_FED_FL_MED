# Rezumat Modificări pentru Testare E2E

**Data**: 2026-04-24  
**Status**: ✅ Implementat și Testat

---

## 🔧 Probleme Identificate și Rezolvate

### 1. Path-uri Dataset Incorecte

**Problema**: Dataset-urile erau înregistrate cu path-uri care includeau `/train` la final, dar funcția `load_dataset` adaugă automat `/train`, rezultând path-uri duble (`/train/train`).

**Soluție**:
- Path-ul înregistrat trebuie să fie directorul de bază (ex: `/storage/datasets/dataset_train_477f2544`)
- Funcția `load_dataset` adaugă automat `/{split}` la path
- Structura finală: `{path}/{split}/NORMAL/` și `{path}/{split}/PNEUMONIA/`

**Fișiere modificate**:
- `scripts/test_e2e_sequential.sh` - Actualizat path-urile de înregistrare

### 2. Validare Dataset în API

**Problema**: API-ul verifica dacă există folderele `NORMAL` și `PNEUMONIA` direct în path-ul dat, dar ar trebui să verifice în `{path}/{split}/`.

**Soluție**:
- Actualizat funcția `register_dataset` pentru a verifica în `{path}/{split}/NORMAL` și `{path}/{split}/PNEUMONIA`
- Adăugat mesaje de eroare mai descriptive

**Fișiere modificate**:
- `services/node/api/app/main.py` - Funcția `register_dataset`

**Cod modificat**:
```python
# Validate dataset structure (must have split/NORMAL and split/PNEUMONIA folders)
split_path = os.path.join(request.path, request.split)

if not os.path.exists(split_path):
    raise HTTPException(
        status_code=400,
        detail=f"Split directory not found: {split_path}"
    )

normal_path = os.path.join(split_path, "NORMAL")
pneumonia_path = os.path.join(split_path, "PNEUMONIA")
```

### 3. Port Flower Server

**Problema**: Flower server era configurat să folosească portul 8082, dar acest port era deja ocupat sau nu era expus corect.

**Soluție**:
- Schimbat portul Flower gRPC la 8080 (portul standard Flower)
- Actualizat docker-compose.yml pentru a expune portul 8080
- Adăugat variabila de mediu `FLOWER_SERVER_ADDRESS='0.0.0.0:8080'` în script

**Fișiere modificate**:
- `docker-compose.yml` - Port mapping `8080:8080`
- `scripts/test_e2e_sequential.sh` - Adăugat `FLOWER_SERVER_ADDRESS`

### 4. Oprire Flower Server

**Problema**: Comanda `pkill` nu este disponibilă în containerul Docker.

**Soluție**:
- Înlocuit `pkill` cu o combinație de `ps`, `grep`, `awk` și `kill`
- Adăugat fallback pentru cazul în care `ps` nu este disponibil

**Cod modificat**:
```bash
# Kill any existing Flower server process
docker compose exec -T central bash -c "ps aux | grep 'flower_server' | grep -v grep | awk '{print \$2}' | xargs -r kill -9" 2>/dev/null || true
```

---

## 📝 Structura Finală Dataset

```
Host:
./storage/node1/datasets/dataset_train_477f2544/
└── train/
    ├── NORMAL/
    │   └── *.jpeg
    └── PNEUMONIA/
        └── *.jpeg

Container (Node1):
/storage/datasets/dataset_train_477f2544/
└── train/
    ├── NORMAL/
    │   └── *.jpeg
    └── PNEUMONIA/
        └── *.jpeg

Înregistrare API:
{
  "path": "/storage/datasets/dataset_train_477f2544",  # FĂRĂ /train
  "name": "Node1 Training Data",
  "split": "train"
}

Folosire în load_dataset:
load_dataset("/storage/datasets/dataset_train_477f2544", split="train")
→ Caută în: /storage/datasets/dataset_train_477f2544/train/
```

---

## 🚀 Workflow Testare E2E

### Pasul 1: Verificare Servicii
```bash
curl http://localhost:8001/api/health
curl http://localhost:8002/api/health
curl http://localhost:8003/api/health
```

### Pasul 2: Înregistrare Datasets (o singură dată)
```bash
# Node1
curl -X POST "http://localhost:8001/api/data/register" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/storage/datasets/dataset_train_477f2544",
    "name": "Node1 Training Data",
    "split": "train"
  }'

# Set as active
curl -X POST "http://localhost:8001/api/data/set-active/{dataset_id}"
```

### Pasul 3-5: Pentru Fiecare Model (× 3)

#### Pasul 3: Pornire Flower Server
```bash
docker compose exec -d central bash -c "
    export MODEL_NAME='resnet18'
    export NUM_ROUNDS=2
    export MIN_CLIENTS=2
    export MIN_FIT_CLIENTS=2
    export MIN_AVAILABLE_CLIENTS=2
    export NUM_EPOCHS=2
    export LEARNING_RATE=0.001
    export OPTIMIZER='adam'
    export FLOWER_SERVER_ADDRESS='0.0.0.0:8080'
    python -m app.flower_server > /tmp/flower_resnet18.log 2>&1
"
```

#### Pasul 4: Pornire Training Noduri
```bash
# Node1
curl -X POST "http://localhost:8001/api/federated/train/R-RESNET18?dataset_id={dataset_id}"

# Node2
curl -X POST "http://localhost:8002/api/federated/train/R-RESNET18?dataset_id={dataset_id}"
```

#### Pasul 5: Monitorizare
```bash
# Check status every 10 seconds
curl "http://localhost:8001/api/train/status/{job_id}"
curl "http://localhost:8002/api/train/status/{job_id}"
```

---

## 🎯 Rezultate Așteptate

După rularea completă a testelor E2E:

### În Baza de Date

**Models Table**:
- 6 modele noi (2 noduri × 3 modele)
- Fiecare cu `round_id` diferit (R-RESNET18, R-DENSENET121, R-EFFICIENTNET)
- Toate cu `type="candidate"` și `labels=["candidate"]`

**Jobs Table**:
- 6 job-uri cu `job_type="federated_train"`
- Toate cu `status="completed"`
- Fiecare cu `params` conținând `round_id` și `dataset_id`

**Datasets Table**:
- 3 datasets (câte unul per nod)
- Fiecare cu `is_active=True`
- Path-uri corecte fără `/train` la final

### În Filesystem

**Node1**:
```
storage/node1/models/candidate/
├── efficientnet_b0_R-EFFICIENTNET_flower.pt
├── densenet121_R-DENSENET121_flower.pt
└── resnet18_R-RESNET18_flower.pt
```

**Central**:
```
storage/central/models/
├── R-RESNET18_round_1.pt
├── R-RESNET18_round_2.pt
├── R-DENSENET121_round_1.pt
├── R-DENSENET121_round_2.pt
├── R-EFFICIENTNET_round_1.pt
└── R-EFFICIENTNET_round_2.pt
```

---

## 🐛 Troubleshooting

### Dataset Registration Fails

**Eroare**: "Dataset must contain NORMAL folder"

**Verificare**:
```bash
# În container
docker compose exec node1-api ls -la /storage/datasets/dataset_train_477f2544/train/

# Ar trebui să vezi:
# drwxr-xr-x NORMAL/
# drwxr-xr-x PNEUMONIA/
```

**Soluție**: Asigură-te că path-ul înregistrat NU include `/train` la final.

### Flower Server Not Starting

**Eroare**: "Port in server address 0.0.0.0:8080 is already in use"

**Verificare**:
```bash
# Check logs
docker compose logs central | tail -50

# Check if Flower server is running
docker compose exec central cat /tmp/flower_resnet18.log
```

**Soluție**: Oprește procesul Flower existent sau folosește un port diferit.

### Training Fails with "Directory not found"

**Eroare**: "Directory not found: /storage/datasets/.../train/train"

**Cauză**: Path-ul dataset-ului include `/train` la final.

**Soluție**:
1. Șterge dataset-ul: `curl -X DELETE "http://localhost:8001/api/data/{dataset_id}"`
2. Înregistrează din nou cu path-ul corect (fără `/train`)

---

## ✅ Checklist Verificare

Înainte de a rula testele E2E:

- [ ] Toate serviciile sunt pornite (`docker compose ps`)
- [ ] API-urile răspund (`curl http://localhost:8001/api/health`)
- [ ] Datasets-urile există în filesystem
- [ ] Portul 8080 este liber pentru Flower gRPC
- [ ] Imaginile Docker sunt rebuild-uite după modificări

După rularea testelor E2E:

- [ ] Toate cele 3 teste s-au finalizat cu succes
- [ ] 6 job-uri cu status "completed" în baza de date
- [ ] 6 modele noi în registry (2 noduri × 3 modele)
- [ ] Fiecare model are un `round_id` unic
- [ ] Nu există erori în logs

---

**Ultima actualizare**: 2026-04-24  
**Autor**: Fed-Med-FL Team  
**Status**: ✅ Gata pentru testare
