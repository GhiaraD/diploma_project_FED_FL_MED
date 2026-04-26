# 🧪 Test Audit Logging prin UI - Ghid Pas cu Pas

## 📋 Pregătire

1. **Deschide browser-ul** la http://localhost:3001
2. **Login** cu:
   - Email: `admin@node1.fed-med-fl.com`
   - Password: `AdminNode1@2026`
3. **Deschide Audit Page** în alt tab: http://localhost:3001/audit

---

## ✅ Teste de Efectuat

### Test 1: Dataset Actions 📁

#### 1.1 Activate Dataset
1. Mergi la **Datasets** page
2. Click pe butonul **"Set Active"** pentru un dataset
3. Refresh pagina de **Audit**
4. **Așteptat:** Ar trebui să vezi un eveniment `dataset_activated` cu:
   - Dataset ID
   - Dataset name
   - Number of samples
   - Timestamp recent

#### 1.2 Register Dataset (dacă ai date disponibile)
1. Mergi la **Datasets** page
2. Click **"Browse Filesystem"**
3. Navighează și găsește un dataset
4. Click **"Register"**
5. Refresh pagina de **Audit**
6. **Așteptat:** Ar trebui să vezi `dataset_registered`

---

### Test 2: Model Actions 🤖

#### 2.1 Promote Model
1. Mergi la **Models** page
2. Găsește un model cu label "candidate" sau "global"
3. Click **"Promote to Active"**
4. Refresh pagina de **Audit**
5. **Așteptat:** Ar trebui să vezi `model_promoted` cu:
   - Model ID
   - Model name
   - Metrics (accuracy, etc.)
   - Version

---

### Test 3: Training Actions 🎓

#### 3.1 Start Local Training
1. Mergi la **Train** page
2. Selectează:
   - Dataset: "Node1 Training Data" (sau alt dataset activ)
   - Model: "ResNet18"
   - Epochs: 1 (pentru test rapid)
   - Batch size: 32
   - Learning rate: 0.001
3. Click **"Start Training"**
4. Refresh pagina de **Audit**
5. **Așteptat:** Ar trebui să vezi `training_started` cu:
   - Job ID
   - Model name
   - Training type: "local"
   - Dataset ID
   - Hyperparameters (epochs, batch_size, learning_rate)

---

### Test 4: Inference Actions 🔍

#### 4.1 Start Inference
1. Mergi la **Inference** page
2. Click **"Browse Images"**
3. Navighează la un folder cu imagini (ex: `/storage/datasets/.../NORMAL/`)
4. Selectează 2-3 imagini
5. Selectează un model deployed
6. Click **"Run Inference"**
7. Refresh pagina de **Audit**
8. **Așteptat:** Ar trebui să vezi `inference_started` cu:
   - Job ID
   - Number of images
   - Model ID
   - Generate Grad-CAM flag

#### 4.2 View Inference Results
1. După ce inference-ul se completează
2. Click pe job pentru a vedea rezultatele
3. Refresh pagina de **Audit**
4. **Așteptat:** Ar trebui să vezi `inference_completed` cu:
   - Job ID
   - Number of predictions
   - Duration (seconds)

---

### Test 5: Federated Learning Actions 🤝

#### 5.1 Join Federated Round
1. Mergi la **Federated** page
2. Dacă există un round activ, click **"Join Round"**
3. SAU creează un round nou de pe pagina centrală
4. Refresh pagina de **Audit**
5. **Așteptat:** Ar trebui să vezi `federated_joined` cu:
   - Round ID
   - Node ID

#### 5.2 Start Federated Training
1. După ce te-ai alăturat unui round
2. Click **"Start Training"**
3. Refresh pagina de **Audit**
4. **Așteptat:** Ar trebui să vezi `federated_training_started` cu:
   - Round ID
   - Job ID
   - Dataset ID
   - Model name
   - Node ID

---

### Test 6: Job Viewing 👁️

#### 6.1 View Job Status
1. Mergi la **Jobs** page
2. Click pe orice job pentru a vedea detaliile
3. Refresh pagina de **Audit**
4. **Așteptat:** Ar trebui să vezi `job_viewed` cu:
   - Job ID
   - Job type
   - Status

---

### Test 7: Authentication Events 🔐

#### 7.1 Logout și Re-login
1. Click pe avatar (colț dreapta-sus)
2. Click **"Logout"**
3. Refresh pagina de **Audit** (va redirecta la login)
4. Login din nou
5. Mergi la **Audit** page
6. **Așteptat:** Ar trebui să vezi:
   - `logout` (de la logout-ul anterior)
   - `login_success` (de la login-ul nou)

#### 7.2 Failed Login (opțional)
1. Logout
2. Încearcă să te loghezi cu parolă greșită
3. Login cu parolă corectă
4. Mergi la **Audit** page
5. **Așteptat:** Ar trebui să vezi:
   - `login_failed` (cu status 401)
   - `login_success` (după login corect)

---

## 🔍 Verificare Audit Page

### Funcționalități de testat:

#### 1. Filtrare după Event Type
- Click pe dropdown-ul **"Event Type"**
- Selectează diferite tipuri (LOGIN_SUCCESS, DATASET_ACTIVATED, etc.)
- Verifică că tabelul se filtrează corect

#### 2. Search
- Scrie în câmpul **"Search"**:
  - "dataset" → ar trebui să vezi toate evenimentele legate de datasets
  - "admin" → ar trebui să vezi toate evenimentele făcute de admin
  - "inference" → ar trebui să vezi toate evenimentele de inference

#### 3. Refresh Button
- Click pe butonul **Refresh** (iconița circulară)
- Verifică că log-urile noi apar

#### 4. Informații afișate
Verifică că fiecare log afișează:
- ✅ Timestamp (dată și oră)
- ✅ Event type (cu icon și culoare)
- ✅ User ID (primele 12 caractere)
- ✅ Endpoint (ex: POST /api/data/set-active)
- ✅ IP Address
- ✅ Status code (cu culoare: verde pentru 200, roșu pentru 4xx/5xx)
- ✅ Duration (în ms)

---

## 📊 Verificare în Baza de Date

După ce ai făcut testele, verifică statisticile:

```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('SELECT event_type, COUNT(*) as count FROM audit_logs GROUP BY event_type ORDER BY count DESC')
print('=== Audit Log Statistics ===')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')
conn.close()
"
```

**Ar trebui să vezi:**
- `login_success`: X
- `logout`: Y
- `dataset_activated`: Z
- `model_promoted`: A (dacă ai promovat un model)
- `training_started`: B (dacă ai început training)
- `inference_started`: C (dacă ai rulat inference)
- `inference_completed`: D (dacă inference-ul s-a completat)
- `federated_joined`: E (dacă te-ai alăturat unui round)
- `job_viewed`: F (dacă ai vizualizat job-uri)

---

## ✅ Checklist de Testare

### Dataset Actions:
- [ ] `dataset_activated` - Activare dataset
- [ ] `dataset_registered` - Înregistrare dataset nou (opțional)
- [ ] `dataset_deleted` - Ștergere dataset (opțional, atenție!)

### Model Actions:
- [ ] `model_promoted` - Promovare model

### Training Actions:
- [ ] `training_started` - Început training local

### Inference Actions:
- [ ] `inference_started` - Început inference
- [ ] `inference_completed` - Inference completat

### Federated Learning:
- [ ] `federated_joined` - Alăturare la round
- [ ] `federated_training_started` - Început training federat

### Job Actions:
- [ ] `job_viewed` - Vizualizare job

### Authentication:
- [ ] `login_success` - Login reușit
- [ ] `logout` - Logout
- [ ] `login_failed` - Login eșuat (opțional)

---

## 🎯 Rezultat Așteptat

După toate testele, pagina de **Audit** ar trebui să arate:

```
=== Security Audit Logs ===

Showing X of Y events

[Tabel cu log-uri]
Timestamp              Event                    User ID          Endpoint                    IP          Status  Duration
2026-04-26 14:30:45   inference_completed ✅   user_136e5e...   GET /api/infer/results     172.18.0.1  200     45ms
2026-04-26 14:30:12   inference_started 🔍     user_136e5e...   POST /api/infer            172.18.0.1  200     120ms
2026-04-26 14:28:33   model_promoted ⬆️        user_136e5e...   POST /api/models/promote   172.18.0.1  200     89ms
2026-04-26 14:25:10   dataset_activated 📁     user_136e5e...   POST /api/data/set-active  172.18.0.1  200     34ms
2026-04-26 14:20:05   login_success ✅         user_136e5e...   POST /api/auth/login       172.18.0.1  200     156ms
...
```

---

## 🐛 Troubleshooting

### Nu văd log-uri noi după acțiuni
1. Verifică că API-ul rulează: `docker ps | grep api`
2. Verifică log-urile API: `docker logs diploma_project_fed_fl_med-node1-api-1 --tail 50`
3. Refresh pagina de Audit (F5 sau butonul Refresh)

### Eroare 403 Forbidden
- Token-ul a expirat (30 minute)
- Logout și login din nou

### Pagina de Audit nu se încarcă
- Verifică că UI-ul rulează: `docker ps | grep ui`
- Verifică log-urile UI: `docker logs diploma_project_fed_fl_med-node1-ui-1 --tail 50`

---

**Succes la testare! 🎉**

Raportează ce tipuri de evenimente ai reușit să generezi!
