# Test Audit Logging - Ghid Complet

## ✅ Status Implementare

### Implementat și Testat:
- ✅ **Authentication Events** (login_success, login_failed, logout)
- ✅ **Dataset Actions** (dataset_activated)

### Implementat dar Netestat:
- 📋 dataset_registered
- 🗑️ dataset_deleted
- ⬆️ model_promoted
- 🎓 training_started
- 🔍 inference_started
- ✅ inference_completed
- 🤝 federated_joined
- 🚀 federated_training_started
- 👁️ job_viewed

---

## 🧪 Plan de Testare

### 1. Dataset Actions

#### Test 1.1: Register Dataset ✅
```bash
# Verifică ce directoare sunt disponibile
curl -X GET "http://localhost:8001/api/data/browse?directory=/storage/datasets" \
  -H "Authorization: Bearer <TOKEN>"

# Înregistrează un dataset nou (dacă există)
curl -X POST "http://localhost:8001/api/data/register" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/storage/datasets/chest_xray",
    "name": "Test Dataset",
    "split": "test"
  }'
```

**Așteptat în audit log:**
- Event: `dataset_registered`
- Details: dataset_id, dataset_name, split, num_samples

#### Test 1.2: Activate Dataset ✅ TESTAT
```bash
curl -X POST "http://localhost:8001/api/data/set-active/dataset_train_824551b0" \
  -H "Authorization: Bearer <TOKEN>"
```

**Rezultat:** ✅ Funcționează! Văzut în audit logs.

#### Test 1.3: Delete Dataset
```bash
curl -X DELETE "http://localhost:8001/api/data/dataset_train_824551b0" \
  -H "Authorization: Bearer <TOKEN>"
```

**Așteptat în audit log:**
- Event: `dataset_deleted`
- Details: dataset_id, dataset_name, split, num_samples

---

### 2. Model Actions

#### Test 2.1: Promote Model
```bash
# Mai întâi, listează modelele
curl -X GET "http://localhost:8001/api/models/registry" \
  -H "Authorization: Bearer <TOKEN>"

# Promovează un model
curl -X POST "http://localhost:8001/api/models/promote" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "<MODEL_ID>"
  }'
```

**Așteptat în audit log:**
- Event: `model_promoted`
- Details: model_id, model_name, version, metrics, round_id

---

### 3. Training Actions

#### Test 3.1: Start Local Training
```bash
curl -X POST "http://localhost:8001/api/train/local" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "dataset_train_824551b0",
    "model_name": "resnet18",
    "num_epochs": 1,
    "batch_size": 32,
    "learning_rate": 0.001
  }'
```

**Așteptat în audit log:**
- Event: `training_started`
- Details: job_id, model_name, training_type: "local", dataset_id, num_epochs, batch_size, learning_rate

---

### 4. Inference Actions

#### Test 4.1: Start Inference
```bash
# Mai întâi, găsește niște imagini
curl -X GET "http://localhost:8001/api/infer/browse?directory=/storage/datasets/chest_xray/train/NORMAL" \
  -H "Authorization: Bearer <TOKEN>"

# Rulează inference
curl -X POST "http://localhost:8001/api/infer" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "image_paths": [
      "/storage/datasets/chest_xray/train/NORMAL/image001.jpeg"
    ],
    "model_id": "<MODEL_ID>",
    "generate_gradcam": true
  }'
```

**Așteptat în audit log:**
- Event: `inference_started`
- Details: job_id, num_images, model_id, generate_gradcam

#### Test 4.2: Get Inference Results
```bash
curl -X GET "http://localhost:8001/api/infer/results/<JOB_ID>" \
  -H "Authorization: Bearer <TOKEN>"
```

**Așteptat în audit log:**
- Event: `inference_completed`
- Details: job_id, num_predictions, duration_seconds

---

### 5. Federated Learning Actions

#### Test 5.1: Join Federated Round
```bash
curl -X POST "http://localhost:8001/api/federated/join/round_test_123" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Așteptat în audit log:**
- Event: `federated_joined`
- Details: round_id, node_id

#### Test 5.2: Start Federated Training
```bash
curl -X POST "http://localhost:8001/api/federated/train/round_test_123?dataset_id=dataset_train_824551b0&model_name=resnet18" \
  -H "Authorization: Bearer <TOKEN>"
```

**Așteptat în audit log:**
- Event: `federated_training_started`
- Details: round_id, job_id, dataset_id, model_name, node_id

---

### 6. Job Actions

#### Test 6.1: View Job Status
```bash
curl -X GET "http://localhost:8001/api/jobs/<JOB_ID>/status" \
  -H "Authorization: Bearer <TOKEN>"
```

**Așteptat în audit log:**
- Event: `job_viewed`
- Details: job_id, job_type, status

---

## 📊 Verificare Audit Logs

### Verifică toate log-urile din baza de date:
```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('SELECT event_type, COUNT(*) as count FROM audit_logs GROUP BY event_type ORDER BY count DESC')
print('Audit log statistics:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')
conn.close()
"
```

### Verifică ultimele 10 log-uri:
```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('SELECT event_type, timestamp, user_id FROM audit_logs ORDER BY timestamp DESC LIMIT 10')
print('Recent audit logs:')
for row in cursor.fetchall():
    print(f'  {row[0]} - {row[1]} - User: {row[2]}')
conn.close()
"
```

---

## 🎯 Test Rapid prin UI

1. **Login** → Ar trebui să vezi `login_success` în audit page
2. **Datasets Page** → Activează un dataset → Ar trebui să vezi `dataset_activated`
3. **Models Page** → Promovează un model → Ar trebui să vezi `model_promoted`
4. **Train Page** → Start training → Ar trebui să vezi `training_started`
5. **Inference Page** → Run inference → Ar trebui să vezi `inference_started` și `inference_completed`
6. **Federated Page** → Join round → Ar trebui să vezi `federated_joined`
7. **Jobs Page** → View job → Ar trebui să vezi `job_viewed`
8. **Logout** → Ar trebui să vezi `logout`

---

## 🔍 Tipuri de Evenimente Implementate

### Authentication (din auth.py):
- ✅ `login_success` - Login reușit
- ✅ `login_failed` - Login eșuat
- ✅ `login_blocked` - Cont blocat
- ✅ `logout` - Logout
- ✅ `password_changed` - Parolă schimbată
- ✅ `user_created` - Utilizator creat (admin)
- ✅ `user_deactivated` - Utilizator dezactivat (admin)
- ✅ `api_key_created` - API key creat (admin)
- ✅ `api_key_revoked` - API key revocat (admin)

### Dataset Actions (din main.py):
- ✅ `dataset_registered` - Dataset înregistrat
- ✅ `dataset_activated` - Dataset activat
- ✅ `dataset_deleted` - Dataset șters

### Model Actions (din main.py):
- ✅ `model_promoted` - Model promovat la deployed

### Training Actions (din main.py):
- ✅ `training_started` - Training local început

### Inference Actions (din main.py):
- ✅ `inference_started` - Inference început
- ✅ `inference_completed` - Inference completat

### Federated Learning (din main.py):
- ✅ `federated_joined` - Node s-a alăturat unui round
- ✅ `federated_training_started` - Training federat început

### Job Actions (din main.py):
- ✅ `job_viewed` - Job vizualizat

---

## ✅ Checklist Final

- [x] Implementat logging pentru datasets
- [x] Implementat logging pentru models
- [x] Implementat logging pentru training
- [x] Implementat logging pentru inference
- [x] Implementat logging pentru federated learning
- [x] Implementat logging pentru jobs
- [x] Testat dataset_activated ✅
- [ ] Testat dataset_registered
- [ ] Testat dataset_deleted
- [ ] Testat model_promoted
- [ ] Testat training_started
- [ ] Testat inference_started
- [ ] Testat inference_completed
- [ ] Testat federated_joined
- [ ] Testat federated_training_started
- [ ] Testat job_viewed

---

**Next Steps:**
1. Testează fiecare tip de acțiune prin UI
2. Verifică că toate apar în pagina de Audit
3. Testează filtrele (search și event type)
4. Verifică că timestamp-urile sunt corecte
5. Verifică că user_id-urile sunt corecte
