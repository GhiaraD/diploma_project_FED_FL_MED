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
- **URL**: http://localhost:8080
- **Health**: http://localhost:8080/health
- **API Docs**: http://localhost:8080/docs

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

## Workflow Federated Learning

### 1. Accesează UI-ul unui nod

Deschide în browser: http://localhost:3001

### 2. Upload Dataset (Studies)

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

### 3. Creează Rundă FL (Central)

```bash
curl -X POST http://localhost:8080/round/create \
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

### 4. Join Round (UI - Federated)

1. Click pe **Federated** în sidebar
2. Introdu Round ID: `R-1`
3. Click **Join Round**
4. Repetă pentru toate nodurile (3001, 3002, 3003)

### 5. Start Training (UI - Federated)

1. În pagina **Federated**
2. Introdu Dataset ID (din Studies)
3. Click **Start Training**
4. Monitorizează progresul în stepper
5. Repetă pentru toate nodurile

### 6. Trigger Aggregation (Central)

```bash
# Așteaptă ca toate nodurile să termine training
# Apoi trigger aggregation
curl -X POST http://localhost:8080/round/R-1/aggregate
```

### 7. View Results

```bash
curl http://localhost:8080/round/R-1/results
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
│                   http://localhost:8080                      │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼────────┐  ┌────▼──────┐  ┌─────▼─────────┐
│   Node 1       │  │  Node 2   │  │   Node 3      │
│  :8001 :3001   │  │ :8002:3002│  │  :8003 :3003  │
│                │  │           │  │               │
│ API + Worker   │  │API+Worker │  │ API + Worker  │
│ UI (Next.js)   │  │UI(Next.js)│  │ UI (Next.js)  │
│ Redis          │  │Redis      │  │ Redis         │
└────────────────┘  └───────────┘  └───────────────┘
```

---

## Ports

| Service | Port | URL |
|---------|------|-----|
| Central | 8080 | http://localhost:8080 |
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
2. **Creează rundă FL** pe Central
3. **Join round** de pe toate nodurile
4. **Start training** pe toate nodurile
5. **Trigger aggregation** pe Central
6. **View results** și metrici
7. **Repeat** pentru mai multe runde (R-2, R-3, etc.)

---

## Resources

- **Documentation**: `docs/`
- **Scripts**: `scripts/`
- **Examples**: `shared/python/node_core/examples/`
- **Tests**: `shared/python/node_core/tests/`

---

**Autor**: Fed-Med-FL Team  
**Versiune**: 0.1.0  
**Status**: ✅ PRODUCTION READY
