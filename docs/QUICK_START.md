# Fed-Med-FL - Quick Start Guide

## Pornire Rapidă

### Folosind Makefile (Recomandat)

```bash
# Pornește toate serviciile
make up

# Verifică statusul
make status

# Testează toate serviciile
make test-all

# Vezi logs
make logs

# Oprește serviciile
make down
```

### Comenzi Disponibile

```bash
make help  # Afișează toate comenzile
```

---

## Servicii Disponibile

### Central Server
- **Management API**: http://localhost:8081
- **Flower gRPC**: localhost:8080
- **Health**: http://localhost:8081/health
- **API Docs**: http://localhost:8081/docs

### Node 1 (Hospital 1)
- **API**: http://localhost:8001
- **UI**: http://localhost:3001
- **Health**: http://localhost:8001/api/health

### Node 2 (Hospital 2)
- **API**: http://localhost:8002
- **UI**: http://localhost:3002
- **Health**: http://localhost:8002/api/health

### Node 3 (Hospital 3)
- **API**: http://localhost:8003
- **UI**: http://localhost:3003
- **Health**: http://localhost:8003/api/health

---

## Workflow Federated Learning (Flower Framework)

### Opțiunea 1: Folosind Flower Server Direct (Recomandat)

#### 1. Upload Datasets la toate nodurile

Accesează UI-ul fiecărui nod și upload dataset:
- http://localhost:3001 (Node1)
- http://localhost:3002 (Node2)
- http://localhost:3003 (Node3)

**Pași**:
1. Click pe **Studies** în sidebar
2. Click pe **Upload Dataset**
3. Selectează split: `train`
4. Alege fișier ZIP cu structura:
   ```
   dataset.zip
   ├── NORMAL/
   │   ├── image1.jpg
   │   └── ...
   └── PNEUMONIA/
       ├── image1.jpg
       └── ...
   ```
5. Click **Upload**
6. Notează `dataset_id` din tabel

#### 2. Start Flower Server (Central)

```bash
# În terminal separat
docker compose exec central python -m app.flower_server
```

**Output așteptat**:
```
======================================================================
FED-MED-FL FLOWER SERVER
======================================================================
Server address: 0.0.0.0:8080
Number of rounds: 5
Minimum clients: 2
Model: resnet18
======================================================================

[Server] Starting Flower server...
[Server] Waiting for 2 clients to connect...
```

#### 3. Start Flower Clients (Nodes)

În terminale separate pentru fiecare nod:

```bash
# Node 1
curl -X POST "http://localhost:8001/api/federated/train/R-FLOWER-1?dataset_id=<DATASET_ID>"

# Node 2
curl -X POST "http://localhost:8002/api/federated/train/R-FLOWER-1?dataset_id=<DATASET_ID>"

# Node 3
curl -X POST "http://localhost:8003/api/federated/train/R-FLOWER-1?dataset_id=<DATASET_ID>"
```

**Notă**: Înlocuiește `<DATASET_ID>` cu ID-ul dataset-ului uploadat.

#### 4. Monitorizează Progresul

Flower Server va afișa progresul în timp real:
```
[ROUND 1]
configure_fit: strategy sampled 3 clients
[FedMedStrategy] Round 1: Aggregating 3 clients
[FedMedStrategy] ✓ Round 1 aggregation complete
[FedMedStrategy] ✓ Model saved: /storage/models/global_R-1.pt

[ROUND 2]
...
```

#### 5. Verifică Rezultatele

După completarea rundelor:
```bash
# Verifică modelele salvate
ls -la storage/central/models/

# Output:
# global_R-0.pt  (initial model)
# global_R-1.pt  (after round 1)
# global_R-2.pt  (after round 2)
# ...
```

### Opțiunea 2: Folosind Management API (Legacy)

#### 1. Creează Rundă FL (Central)

```bash
curl -X POST http://localhost:8081/round/create \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "R-1",
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

#### 2. Join Round (UI - Federated)

1. Click pe **Federated** în sidebar
2. Introdu Round ID: `R-1`
3. Click **Join Round**
4. Repetă pentru toate nodurile (3001, 3002, 3003)

#### 3. Start Training (UI - Federated)

1. În pagina **Federated**
2. Introdu Dataset ID (din Studies)
3. Click **Start Training**
4. Monitorizează progresul în stepper
5. Repetă pentru toate nodurile

---

## Testing Rapid cu Simulare

Pentru testare rapidă fără Docker:

```bash
# Rulează simulare cu clienți virtuali
python3 shared/python/node_core/examples/flower_simulation.py \
  --clients 3 \
  --rounds 3 \
  --epochs 2

# Output:
# ✅ 3 runde completate
# ✅ Modele salvate: global_R-0.pt, global_R-1.pt, global_R-2.pt
```

---

## Comenzi Utile

### Logs

```bash
# Toate serviciile
make logs

# Doar Central
make logs-central

# Doar Node1
make logs-node1

# Doar Node2
make logs-node2

# Doar Node3
make logs-node3
```

### Restart

```bash
# Toate serviciile
make restart

# Doar Central
make restart-central

# Doar Node1
make restart-node1
```

### Build

```bash
# Build toate
make build

# Build doar Central
make build-central

# Build doar Nodes
make build-nodes

# Build doar UI
make build-ui
```

### Testing

```bash
# Test toate
make test-all

# Test Central
make test-central

# Test Node APIs
make test-api

# Test UIs
make test-ui

# Demo FL workflow
make demo
```

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

### API nu răspunde

```bash
# Verifică status
make status

# Restart serviciu specific
make restart-node1
```

### Worker nu procesează jobs

```bash
# Verifică logs worker
docker compose logs -f node1-worker

# Verifică Redis
docker compose logs -f node1-redis

# Restart worker
docker compose restart node1-worker
```

### UI nu se încarcă

```bash
# Verifică logs UI
docker compose logs -f node1-ui

# Rebuild UI
make build-ui
docker compose up -d node1-ui
```

---

## Cleanup

```bash
# Oprește serviciile
make down

# Oprește și șterge volumes
make down-clean

# Cleanup complet (include images)
make clean
```

---

## Development

### Rebuild după modificări cod

```bash
# Rebuild serviciu specific
docker compose build node1-api
docker compose up -d node1-api

# Sau folosește Makefile
make build-nodes
make restart
```

### Hot reload (UI)

UI-ul folosește Next.js dev mode cu hot reload automat.

### Logs în timp real

```bash
# Toate serviciile
make logs

# Serviciu specific
docker compose logs -f node1-api
```

---

## Arhitectură

```
┌─────────────────────────────────────────────────────────────┐
│                    Central FL Server                         │
│              http://localhost:8081 (Management)              │
│              localhost:8080 (Flower gRPC)                    │
└────────────────────────┬────────────────────────────────────┘
                         │ gRPC (Flower Protocol)
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼────────┐  ┌────▼──────┐  ┌─────▼─────────┐
│   Node 1       │  │  Node 2   │  │   Node 3      │
│  :8001 :3001   │  │ :8002:3002│  │  :8003 :3003  │
│                │  │           │  │               │
│ API + Worker   │  │API+Worker │  │ API + Worker  │
│ Flower Client  │  │Flower Cl. │  │ Flower Client │
│ UI (Next.js)   │  │UI(Next.js)│  │ UI (Next.js)  │
│ Redis          │  │Redis      │  │ Redis         │
└────────────────┘  └───────────┘  └───────────────┘
```

---

## Ports

| Service | Port | URL |
|---------|------|-----|
| Central Management | 8081 | http://localhost:8081 |
| Central Flower gRPC | 8080 | localhost:8080 |
| Node1 API | 8001 | http://localhost:8001 |
| Node1 UI | 3001 | http://localhost:3001 |
| Node1 Redis | 63791 | localhost:63791 |
| Node2 API | 8002 | http://localhost:8002 |
| Node2 UI | 3002 | http://localhost:3002 |
| Node2 Redis | 63792 | localhost:63792 |
| Node3 API | 8003 | http://localhost:8003 |
| Node3 UI | 3003 | http://localhost:3003 |
| Node3 Redis | 63793 | localhost:63793 |

---

## Next Steps

1. **Upload datasets** la toate nodurile
2. **Start Flower Server** pe Central
3. **Start Flower Clients** pe toate nodurile
4. **Monitorizează progresul** în logs
5. **Verifică modelele salvate** în storage/central/models/
6. **Repeat** pentru mai multe runde

**Sau folosește simularea**:
```bash
python3 shared/python/node_core/examples/flower_simulation.py --clients 3 --rounds 3
```

---

**Autor**: Fed-Med-FL Team  
**Versiune**: 0.2.0  
**FL Framework**: Flower 1.29+  
**Status**: ✅ PRODUCTION READY
