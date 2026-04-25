# Ghid Testare End-to-End (E2E)

**Data**: 2026-04-24  
**Versiune**: 1.0  
**Status**: ✅ Implementat

---

## 📋 Prezentare Generală

Acest ghid descrie procesul de testare End-to-End (E2E) pentru Fed-Med-FL, care testează întregul flux de Federated Learning cu 3 modele diferite, secvențial.

---

## 🎯 Obiective Testare E2E

Testele E2E verifică:

1. **Înregistrarea datasets** - Fiecare nod înregistrează și activează un dataset
2. **Flower Server** - Pornește corect cu configurația pentru fiecare model
3. **Flower Clients** - Nodurile se conectează și participă la training
4. **Training FL** - 2 runde × 2 epoci pentru fiecare model
5. **Salvare modele** - Modelele sunt salvate în registry ca "candidate"
6. **Jobs tracking** - Toate job-urile sunt înregistrate în baza de date

---

## 🧪 Structura Testelor

### Test 1: ResNet18
- **Model**: ResNet18 (pretrained)
- **Round ID**: R-RESNET18
- **Noduri**: Node1 + Node2 (Node3 nu participă)
- **Configurație**: 2 runde, 2 epoci, batch_size=16, lr=0.001

### Test 2: DenseNet121
- **Model**: DenseNet121 (pretrained)
- **Round ID**: R-DENSENET121
- **Noduri**: Node1 + Node2 (Node3 nu participă)
- **Configurație**: 2 runde, 2 epoci, batch_size=16, lr=0.001

### Test 3: EfficientNet-B0
- **Model**: EfficientNet-B0 (pretrained)
- **Round ID**: R-EFFICIENTNET
- **Noduri**: Node1 + Node2 (Node3 nu participă)
- **Configurație**: 2 runde, 2 epoci, batch_size=16, lr=0.001

---

## 🚀 Rulare Teste E2E

### Prerequisite

1. **Serviciile trebuie să fie pornite**:
   ```bash
   make up
   ```

2. **Datasets trebuie să existe**:
   ```bash
   # Verifică dacă există
   ls -la storage/datasets/dataset_train_477f2544/train/
   
   # Dacă nu există, creează-le
   make create-datasets
   ```

### Rulare Automată

```bash
# Rulează toate cele 3 teste secvențial
./scripts/test_e2e_sequential.sh
```

### Durata Estimată

- **Per test**: 5-10 minute (depinde de hardware)
- **Total**: 15-30 minute pentru toate cele 3 teste

---

## 📊 Ce Face Scriptul

### Pasul 1: Verificare Servicii

Verifică că toate serviciile sunt pornite:
- Node1 API (http://localhost:8001)
- Node2 API (http://localhost:8002)
- Node3 API (http://localhost:8003)

### Pasul 2: Înregistrare Datasets (o singură dată)

Pentru fiecare nod:
1. Înregistrează dataset-ul din path-ul de bază (FĂRĂ `/train` la final)
   - Node1: `/storage/node1/datasets/dataset_train_477f2544`
   - Node2: `/storage/node2/datasets/dataset_train_fb09a934`
   - Node3: `/storage/node3/datasets/dataset_train_f1ea778b`
2. Setează dataset-ul ca activ (`is_active=True`)
3. Salvează `dataset_id` pentru utilizare ulterioară

**Important**: 
- Path-ul trebuie să fie directorul de bază care conține folderul `train/`
- Funcția `load_dataset` va adăuga automat `/train` la path
- Structura așteptată: `{path}/train/NORMAL/` și `{path}/train/PNEUMONIA/`
- Datasets sunt înregistrate o singură dată la început, apoi refolosite pentru toate cele 3 teste

### Pasul 3-6: Pentru Fiecare Model (Repetat × 3)

#### Pasul 3: Pornire Flower Server

```bash
docker compose exec -d central bash -c "
    export MODEL_NAME='resnet18' && \
    export NUM_ROUNDS=2 && \
    export MIN_CLIENTS=2 && \
    export MIN_FIT_CLIENTS=2 && \
    export MIN_AVAILABLE_CLIENTS=2 && \
    export NUM_EPOCHS=2 && \
    export LEARNING_RATE=0.001 && \
    export OPTIMIZER='adam' && \
    python -m app.flower_server
"
```

#### Pasul 4: Pornire Training Node1

```bash
curl -X POST "http://localhost:8001/api/federated/train/R-RESNET18?dataset_id=${DATASET1_ID}"
```

Acest endpoint:
1. Creează un job în baza de date (`job_type="federated_train"`)
2. Pornește un task Celery care:
   - Citește dataset-ul activ din baza de date
   - Pornește Flower client care se conectează la server
   - Participă la training FL

#### Pasul 5: Pornire Training Node2

Similar cu Node1, dar pe portul 8002.

#### Pasul 6: Monitorizare Progres

Scriptul verifică statusul job-urilor la fiecare 10 secunde:

```bash
curl "http://localhost:8001/api/train/status/${JOB1_ID}"
curl "http://localhost:8002/api/train/status/${JOB2_ID}"
```

Statusuri posibile:
- `pending` - Job creat, așteaptă să înceapă
- `running` - Training în curs
- `completed` - Training finalizat cu succes
- `failed` - Training eșuat

#### Pasul 7: Oprire Flower Server

După fiecare test, Flower server este oprit pentru a pregăti următorul test:

```bash
docker compose exec -T central pkill -f "flower_server"
```

---

## 🔍 Verificare Rezultate

### 1. Verificare în UI

#### Models Page
```
http://localhost:3001/models
```

Ar trebui să vezi:
- 3 modele noi în registry (câte unul pentru fiecare test)
- Fiecare model are label "candidate"
- Fiecare model are `round_id` diferit (R-RESNET18, R-DENSENET121, R-EFFICIENTNET)

#### Jobs Page
```
http://localhost:3001/jobs
```

Ar trebui să vezi:
- 6 job-uri totale (2 noduri × 3 modele)
- Toate cu `job_type="federated_train"`
- Toate cu `status="completed"`

#### Federated Page
```
http://localhost:3001/federated
```

Ar trebui să vezi istoricul rundelor FL.

### 2. Verificare în Baza de Date

```bash
# Node1 - Verifică modele
docker compose exec node1-api sqlite3 /storage/node1.db "SELECT model_id, model_name, version, type, labels FROM models;"

# Node1 - Verifică jobs
docker compose exec node1-api sqlite3 /storage/node1.db "SELECT job_id, job_type, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 10;"

# Node1 - Verifică datasets
docker compose exec node1-api sqlite3 /storage/node1.db "SELECT dataset_id, name, is_active, num_samples FROM datasets;"
```

### 3. Verificare Fișiere Salvate

```bash
# Verifică modelele salvate
ls -lh storage/node1/models/candidate/
ls -lh storage/node2/models/candidate/

# Verifică modelele globale (pe central)
ls -lh storage/central/models/
```

---

## 🐛 Troubleshooting

### Problema: "Dataset not found"

**Cauză**: Dataset-ul nu este înregistrat sau nu este activ.

**Soluție**:
```bash
# Verifică datasets înregistrate
curl http://localhost:8001/api/data/list

# Verifică dataset activ
curl http://localhost:8001/api/data/active

# Setează un dataset ca activ
curl -X POST http://localhost:8001/api/data/set-active/{dataset_id}
```

### Problema: "Flower server not responding"

**Cauză**: Flower server nu s-a pornit sau nu este accesibil.

**Soluție**:
```bash
# Verifică logs Flower server
docker compose logs -f central

# Verifică dacă procesul rulează
docker compose exec central ps aux | grep flower_server

# Repornește manual
docker compose exec -d central bash -c "
    export MODEL_NAME='resnet18' && \
    export NUM_ROUNDS=2 && \
    python -m app.flower_server
"
```

### Problema: "Training timeout"

**Cauză**: Training durează prea mult (>15 minute).

**Soluție**:
1. Verifică dacă GPU este disponibil:
   ```bash
   docker compose exec node1-worker python -c "import torch; print(torch.cuda.is_available())"
   ```

2. Reduce numărul de epoci sau batch size în script

3. Verifică logs pentru erori:
   ```bash
   docker compose logs -f node1-worker
   ```

### Problema: "Job status stuck in 'running'"

**Cauză**: Worker-ul s-a blocat sau a eșuat fără să actualizeze statusul.

**Soluție**:
```bash
# Verifică logs worker
docker compose logs -f node1-worker

# Repornește worker-ul
docker compose restart node1-worker

# Verifică Celery tasks
docker compose exec node1-worker celery -A app.tasks inspect active
```

---

## 📈 Metrici de Succes

Un test E2E este considerat reușit dacă:

✅ Toate cele 3 teste se finalizează fără erori  
✅ Toate job-urile au status "completed"  
✅ Toate modelele sunt salvate în registry  
✅ Fiecare model are un `round_id` unic  
✅ Datasets sunt înregistrate și active pe toate nodurile  
✅ Nu există erori în logs  

---

## 🔄 Arhitectura Testelor

```
┌─────────────────────────────────────────────────────────────┐
│                    Test E2E Sequential                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  1. Verificare Servicii (o dată)      │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  2. Înregistrare Datasets (o dată)    │
        │     - Node1: dataset_train_xxx        │
        │     - Node2: dataset_train_xxx        │
        │     - Node3: dataset_train_xxx        │
        │     - Set active pe toate nodurile    │
        └───────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌───────────────┐                     ┌───────────────┐
│  Test 1       │                     │  Test 2       │
│  ResNet18     │  ──────────────────▶│  DenseNet121  │
│  R-RESNET18   │                     │  R-DENSENET   │
└───────────────┘                     └───────────────┘
                                              │
                                              ▼
                                      ┌───────────────┐
                                      │  Test 3       │
                                      │  EfficientNet │
                                      │  R-EFFICIENT  │
                                      └───────────────┘

Fiecare Test:
  1. Pornește Flower Server (cu MODEL_NAME specific)
  2. Node1 pornește training (folosește dataset activ)
  3. Node2 pornește training (folosește dataset activ)
  4. Monitorizează progres (polling la 10s)
  5. Verifică rezultate
  6. Oprește Flower Server
  7. Așteaptă 15s înainte de următorul test
```

---

## 📝 Diferențe față de Implementarea Anterioară

### Înainte (Implementare Veche)

- Datasets erau uploadate ca ZIP pentru fiecare test
- Fiecare nod avea propriul dataset separat
- Nu exista concept de "dataset activ"
- Round ID-uri erau generice (R-1, R-2, R-3)

### Acum (Implementare Nouă)

- ✅ Datasets sunt înregistrate o singură dată la început
- ✅ Fiecare nod folosește dataset-ul activ din baza de date
- ✅ Dataset-ul activ este setat explicit (`is_active=True`)
- ✅ Round ID-uri sunt descriptive (R-RESNET18, R-DENSENET121, R-EFFICIENTNET)
- ✅ Flower client citește automat dataset-ul activ
- ✅ Nu mai este nevoie să specificăm `dataset_id` în fiecare request (se folosește cel activ)

---

## 🎓 Învățăminte Cheie

1. **Dataset Management**: Sistemul nou permite înregistrarea datasets din filesystem fără upload
2. **Active Dataset**: Conceptul de dataset activ simplifică workflow-ul
3. **Flower Integration**: Flower client se conectează automat la server și folosește dataset-ul activ
4. **Sequential Testing**: Testele secvențiale permit verificarea mai multor modele fără interferențe
5. **Job Tracking**: Toate operațiunile sunt înregistrate în baza de date pentru audit

---

## 📚 Resurse Suplimentare

- **PROJECT_OVERVIEW.md** - Overview complet al proiectului
- **FLOWER_MIGRATION_SUMMARY.md** - Detalii despre migrarea la Flower
- **HOW_TO_USE_OBSERVABILITY.md** - Ghid pentru Jobs & Management UI
- **scripts/README_E2E_TESTS.md** - Documentație scripturi E2E

---

**Ultima actualizare**: 2026-04-24  
**Autor**: Fed-Med-FL Team  
**Status**: ✅ Gata pentru utilizare
