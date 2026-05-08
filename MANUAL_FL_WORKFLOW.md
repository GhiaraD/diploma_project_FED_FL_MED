# Manual Federated Learning Workflow

Acest document descrie workflow-ul manual pentru rularea unui training FL cu Flower Server.

## 🎯 De ce manual?

Flower Server trebuie pornit **după** ce nodurile sunt gata să se conecteze, pentru a evita timeout-ul înainte ca clienții să fie disponibili.

## 📋 Pași pentru rularea FL

### 1. Pornește toate serviciile (fără Flower Server)

```bash
docker compose up -d
```

Acest lucru pornește:
- ✅ Central Management API (port 8081)
- ✅ Node 1, 2, 3 (API + Worker + UI + Redis)
- ❌ Flower Server (va fi pornit manual)

### 2. Verifică că serviciile sunt UP

```bash
docker compose ps
```

Toate serviciile ar trebui să fie `Up`.

### 3. Înregistrează și activează dataset-urile

**Opțiune A: Din UI**
- Accesează http://localhost:3001 (Node 1)
- Accesează http://localhost:3002 (Node 2)
- Login cu: `admin@node1.fed-med-fl.com` / `AdminNode1@2026`
- Mergi la "Datasets" și înregistrează dataset-urile

**Opțiune B: Cu script**
```bash
python3 scripts/register_datasets.sh
```

### 4. Creează un training round

```bash
curl -X POST "http://localhost:8081/round/create" \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "test_round_1",
    "model_name": "efficientnet_b0",
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

### 5. Înregistrează nodurile pentru round

```bash
# Node 1
curl -X POST "http://localhost:8081/round/test_round_1/join" \
  -H "Content-Type: application/json" \
  -d '{"node_id": "node1"}'

# Node 2
curl -X POST "http://localhost:8081/round/test_round_1/join" \
  -H "Content-Type: application/json" \
  -d '{"node_id": "node2"}'
```

### 6. Pornește training pe noduri

**Node 1:**
```bash
TOKEN1=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
  -d "username=admin@node1.fed-med-fl.com&password=AdminNode1@2026" | \
  jq -r '.access_token')

curl -X POST "http://localhost:8001/api/federated/train/test_round_1?dataset_id=<DATASET_ID>" \
  -H "Authorization: Bearer $TOKEN1"
```

**Node 2:**
```bash
TOKEN2=$(curl -s -X POST "http://localhost:8002/api/auth/login" \
  -d "username=admin@node2.fed-med-fl.com&password=AdminNode2@2026" | \
  jq -r '.access_token')

curl -X POST "http://localhost:8002/api/federated/train/test_round_1?dataset_id=<DATASET_ID>" \
  -H "Authorization: Bearer $TOKEN2"
```

### 7. 🌸 Pornește Flower Server

**IMPORTANT:** Pornește Flower Server IMEDIAT după ce ai pornit training-ul pe noduri!

```bash
./scripts/start_flower_server.sh
```

Sau direct:
```bash
docker compose exec central python -m app.flower_server \
  --num-rounds 2 \
  --model-name efficientnet_b0 \
  --num-epochs 2 \
  --min-available-clients 2 \
  --min-fit-clients 2
```

### 8. Monitorizează progresul

**Flower Server logs:**
```bash
# Logs-urile vor apărea în terminalul unde ai pornit Flower Server
```

**Node logs:**
```bash
docker compose logs -f node1-worker node2-worker
```

**Status round:**
```bash
curl "http://localhost:8081/round/test_round_1/status"
```

## 🔄 Workflow complet automatizat (E2E Test)

Pentru testare automată, folosește:

```bash
python3 test_e2e_efficientnet.py
```

**NOTĂ:** Testul E2E va eșua pentru că Flower Server nu este pornit automat. Trebuie să:
1. Rulezi testul până la pasul 6 (training pornit pe noduri)
2. Pornești manual Flower Server cu `./scripts/start_flower_server.sh`
3. Aștepți ca training-ul să se termine

## 📊 Verificare rezultate

După ce Flower Server termină:

```bash
# Verifică modelele globale
ls -la storage/central/models/

# Verifică modelele locale
ls -la storage/node1/models/
ls -la storage/node2/models/
```

## 🔐 Securitate

- ✅ **mTLS activat** - Flower Server și clienții folosesc certificate SSL
- ✅ **JWT Authentication** - API-urile necesită autentificare
- ✅ **Payload Signing** - Opțional, pentru verificarea integrității

## 🐛 Troubleshooting

### Flower Server nu se conectează la noduri

```bash
# Verifică că portul 8080 este deschis
docker compose exec central netstat -tlnp | grep 8080

# Verifică certificatele
docker compose exec central ls -la /certificates/central/
docker compose exec node1-worker ls -la /certificates/nodes/node1/
```

### Training eșuează pe noduri

```bash
# Verifică logs-urile worker
docker compose logs node1-worker --tail=50

# Verifică dataset-ul activ
curl "http://localhost:8001/api/data/active" \
  -H "Authorization: Bearer $TOKEN1"
```

### Connection refused

- Asigură-te că Flower Server este pornit DUPĂ ce nodurile au început training-ul
- Verifică că SSL este activat pe toate nodurile (`ENABLE_SSL=true`)

## 📝 Note

- Flower Server trebuie pornit manual pentru fiecare sesiune de training
- Certificatele SSL sunt valabile 1 an (regenerează cu `python3 scripts/generate_certificates.py`)
- Pentru producție, consideră folosirea unui orchestrator (Kubernetes) pentru gestionarea automată a Flower Server
