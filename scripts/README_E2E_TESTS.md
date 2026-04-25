# E2E Sequential Testing Guide

## 📋 Overview

Acest script rulează 3 teste E2E secvențiale pentru Fed-Med-FL, fiecare cu un model diferit:
1. **Test 1**: ResNet18 (Round R-1)
2. **Test 2**: DenseNet121 (Round R-2)  
3. **Test 3**: EfficientNet-B0 (Round R-3)

## ⚙️ Configurare

Fiecare test:
- **2 runde** de training federat
- **2 epoci** per rundă
- **2 noduri participante** (Node1 & Node2)
- **Node3 NU participă** (pentru a simula scenarii reale)
- **Batch size**: 16
- **Learning rate**: 0.001

## 🚀 Cum să Rulezi

### 1. Asigură-te că toate serviciile rulează

```bash
docker compose up -d
```

Verifică că toate serviciile sunt pornite:
```bash
docker compose ps
```

Ar trebui să vezi:
- central (Management API + Flower Server)
- node1-api, node1-worker, node1-ui
- node2-api, node2-worker, node2-ui
- node3-api, node3-worker, node3-ui

### 2. Rulează testele

```bash
cd scripts
./test_e2e_sequential.sh
```

## 📊 Ce Face Scriptul

### Pentru Fiecare Test:

**Step 1: Register Datasets** (doar prima dată)
- Înregistrează datasets pe Node1 și Node2
- Setează datasets ca active

**Step 2: Start Flower Server**
- Pornește Flower gRPC server cu modelul specificat
- Configurează numărul de runde și clienți

**Step 3-4: Start FL Training**
- Node1 începe training cu dataset-ul său
- Node2 începe training cu dataset-ul său
- Node3 NU participă

**Step 5: Monitor Progress**
- Verifică status-ul job-urilor la fiecare 10 secunde
- Afișează progresul în timp real
- Timeout după 10 minute

**Step 6: Verify Results**
- Verifică accuracy pentru fiecare nod
- Afișează rezultatele

## 📈 Output Așteptat

```
========================================
Fed-Med-FL E2E Sequential Testing
========================================

Configuration:
  - 3 Tests (ResNet18, DenseNet121, EfficientNet-B0)
  - 2 Rounds per test
  - 2 Epochs per round
  - 2 Nodes participating (Node1 & Node2)
  - Node3 will NOT participate

Checking if services are running...
✓ All services are running

Step 1: Registering datasets on nodes...
✓ Node1 Dataset ID: dataset_train_abc123
✓ Node1 dataset set as active
✓ Node2 Dataset ID: dataset_train_def456
✓ Node2 dataset set as active

========================================
Test 1: resnet18
========================================

Step 2: Starting Flower Server (Round R-1)...
✓ Flower server started

Step 3: Starting FL training on Node1...
✓ Node1 training started - Job ID: fl_train_R-1_abc123

Step 4: Starting FL training on Node2...
✓ Node2 training started - Job ID: fl_train_R-1_def456

Step 5: Monitoring training progress...
  Node1: running | Node2: running | Elapsed: 0s
  Node1: running | Node2: running | Elapsed: 10s
  ...
  Node1: completed | Node2: completed | Elapsed: 120s

✓ Both nodes completed training!

Step 6: Verifying results...
✓ Node1 Accuracy: 85.23%
✓ Node2 Accuracy: 84.67%

========================================
Test 1 (resnet18) COMPLETED!
========================================

[Similar output for Test 2 and Test 3...]

========================================
ALL TESTS COMPLETED SUCCESSFULLY!
========================================

Summary:
  ✓ Test 1: ResNet18 (Round R-1)
  ✓ Test 2: DenseNet121 (Round R-2)
  ✓ Test 3: EfficientNet-B0 (Round R-3)

You can now check:
  - Federated page: http://localhost:3001/federated
  - Models page: http://localhost:3001/models
  - Jobs page: http://localhost:3001/jobs
```

## ⏱️ Durata Estimată

- **Per test**: ~3-5 minute (depinde de hardware)
- **Total**: ~10-15 minute pentru toate 3 testele

## 🔍 Verificare Rezultate

După ce testele se termină, poți verifica rezultatele în UI:

### 1. Federated Learning History
```
http://localhost:3001/federated
```
Vei vedea 3 runde (R-1, R-2, R-3) cu:
- Status: completed
- Participated: Yes (pentru Node1 & Node2)
- Model info
- Accuracy metrics

### 2. Models Registry
```
http://localhost:3001/models
```
Vei vedea 3 modele noi (câte unul per rundă):
- ResNet18 model (din R-1)
- DenseNet121 model (din R-2)
- EfficientNet-B0 model (din R-3)

### 3. Jobs Management
```
http://localhost:3001/jobs
```
Vei vedea 6 job-uri (2 per rundă):
- fl_train_R-1_* (Node1 & Node2)
- fl_train_R-2_* (Node1 & Node2)
- fl_train_R-3_* (Node1 & Node2)

## 🐛 Troubleshooting

### Serviciile nu pornesc
```bash
docker compose down
docker compose up -d
sleep 10  # Wait for services to start
```

### Datasets nu se înregistrează
Verifică că există datasets în storage:
```bash
ls -la storage/node1/datasets/
```

### Training timeout
Crește `MAX_WAIT` în script (default: 600 secunde = 10 minute)

### Flower server nu pornește
Verifică logs:
```bash
docker compose logs central
```

## 📝 Notițe

- Scriptul așteaptă ca fiecare test să se termine înainte de a începe următorul
- Node3 este disponibil dar NU participă (pentru a testa scenarii cu noduri inactive)
- Datasets sunt înregistrate o singură dată la început
- Fiecare test folosește același dataset dar un model diferit
- Rezultatele sunt salvate în database și pot fi văzute în UI

## 🎯 Next Steps

După ce testele se termină cu succes:
1. Explorează UI-ul pentru a vedea rezultatele
2. Promovează unul din modele ca "active" în Models page
3. Rulează inference cu modelul activ
4. Verifică Jobs page pentru detalii despre fiecare task
