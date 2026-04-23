# Ghid de Utilizare - Funcționalitate Observabilitate

**Versiune**: 1.0.0  
**Data**: 2026-04-23  
**Status**: ✅ Production Ready

---

## 🎯 Ce Este Funcționalitatea de Observabilitate?

Funcționalitatea de **Observabilitate și Management** îți permite să:
- 📊 Vezi toate job-urile din sistem (training, inference, federated learning)
- 🔍 Monitorizezi statusul fiecărui job în timp real
- 📝 Vezi logs-urile job-urilor (static și live streaming)
- 🎮 Controlezi streaming-ul (pause, resume, clear, export)
- 🔄 Auto-refresh pentru a vedea actualizări automate

---

## 🚀 Quick Start

### Pas 1: Accesează UI-ul

Deschide browser-ul și navighează la:
```
Node 1: http://localhost:3001/jobs
Node 2: http://localhost:3002/jobs
Node 3: http://localhost:3003/jobs
```

### Pas 2: Vezi Job-urile

Vei vedea un tabel cu toate job-urile:
- **Job ID**: Identificator unic
- **Type**: train, infer, federated_train
- **Status**: pending, running, completed, failed
- **Created**: Când a fost creat
- **Actions**: Buton pentru a vedea logs

### Pas 3: Filtrează Job-urile

Folosește dropdown-urile pentru a filtra:
- **Status**: All, Pending, Running, Completed, Failed
- **Type**: All, Train, Infer, Federated Train

### Pas 4: Vezi Logs

Click pe butonul 👁️ (View Logs) pentru a deschide dialog-ul cu logs.

---

## 📊 Interfața Utilizator

### Tabel Jobs

```
┌─────────────────────────────────────────────────────────────┐
│  Jobs & Management                    [Auto-refresh] [🔄]   │
├─────────────────────────────────────────────────────────────┤
│  Filters: [All Status ▼] [All Types ▼]                      │
│                                                               │
│  Job ID              Type      Status    Created    Actions  │
│  ─────────────────────────────────────────────────────────  │
│  fl_train_R-3...    Federated  🟢 Running  2m ago    [👁️]   │
│  train_local...     Train      ✅ Complete 5m ago    [👁️]   │
│  infer_xyz...       Infer      ❌ Failed   10m ago   [👁️]   │
└─────────────────────────────────────────────────────────────┘
```

### Dialog Logs

```
┌─────────────────────────────────────────────────────────────┐
│  Job Logs - fl_train_R-3_aad96d48                      [X]   │
├─────────────────────────────────────────────────────────────┤
│  [Static Logs] [Live Stream]                                 │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ [17:10:45] [node1] Starting local training...        │  │
│  │ [17:10:46] Training:  10%|█  | 4/44 [00:11<01:58]   │  │
│  │ [17:10:47] Training:  20%|██ | 8/44 [00:22<01:30]   │  │
│  │ [17:10:48] ✓ Training complete: 95.11% accuracy     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  [⏸️ Pause] [🗑️ Clear] [💾 Export] [Auto-scroll ✓]          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎮 Funcționalități Detaliate

### 1. Auto-Refresh

**Ce face**: Actualizează automat lista de job-uri la fiecare 5 secunde

**Cum să folosești**:
- Toggle-ul "Auto-refresh" este activat by default
- Click pe toggle pentru a opri/porni
- Când este activ, vezi un indicator de loading

**Când să folosești**:
- Când monitorizezi job-uri active
- Când aștepți ca un job să se completeze

### 2. Filtrare Job-uri

**Filtrare după Status**:
- **All**: Vezi toate job-urile
- **Pending**: Job-uri în așteptare
- **Running**: Job-uri active
- **Completed**: Job-uri finalizate cu succes
- **Failed**: Job-uri eșuate

**Filtrare după Tip**:
- **All**: Toate tipurile
- **Train**: Training local
- **Infer**: Inference cu Grad-CAM
- **Federated Train**: Federated Learning

**Combinare filtre**:
```
Status: Running + Type: Federated Train
→ Vezi doar job-urile FL active
```

### 3. Static Logs

**Pentru**: Job-uri completate sau failed

**Ce afișează**:
- Snapshot-ul final al logs-urilor
- Ultimele 100 linii (default)
- Timestamp pentru fiecare linie

**Cum să folosești**:
1. Click pe 👁️ pentru un job completat
2. Tab-ul "Static Logs" este selectat automat
3. Scroll prin logs
4. Click "Export" pentru a descărca

### 4. Live Stream Logs

**Pentru**: Job-uri running

**Ce afișează**:
- Logs în timp real folosind Server-Sent Events
- Actualizări automate când apar logs noi
- Progress indicators pentru training

**Controale disponibile**:

#### ⏸️ Pause/Resume
- **Pause**: Oprește streaming-ul temporar
- **Resume**: Reia streaming-ul
- Logs-urile nu se pierd, doar nu mai apar noi

#### 🗑️ Clear
- Șterge toate logs-urile din viewer
- Nu afectează logs-urile reale
- Util pentru a curăța ecranul

#### 💾 Export
- Descarcă logs-urile ca fișier .txt
- Numele: `job-{job_id}-logs.txt`
- Include toate logs-urile vizibile

#### Auto-scroll
- Toggle pentru scroll automat
- Când este activ, scroll-ul merge automat la ultimul log
- Dezactivează pentru a citi logs-uri vechi

---

## 📝 Exemple de Utilizare

### Exemplu 1: Monitorizare Training Local

**Scenariu**: Ai pornit un training local și vrei să vezi progresul

**Pași**:
1. Navighează la http://localhost:3001/jobs
2. Găsește job-ul de training (Type: Train, Status: Running)
3. Click pe 👁️ (View Logs)
4. Selectează tab-ul "Live Stream"
5. Vezi progresul în timp real:
   ```
   Training:  10%|█         | 4/44 [00:11<01:58]
   Training:  20%|██        | 8/44 [00:22<01:30]
   Training:  30%|███       | 12/44 [00:33<01:15]
   ```
6. Când se completează, vezi:
   ```
   ✓ Training complete: 95.11% accuracy
   ```

### Exemplu 2: Debugging Job Eșuat

**Scenariu**: Un job a eșuat și vrei să vezi de ce

**Pași**:
1. Filtrează după Status: Failed
2. Găsește job-ul eșuat
3. Click pe 👁️ (View Logs)
4. Tab-ul "Static Logs" afișează logs-urile
5. Caută eroarea:
   ```
   [ERROR] CUDA out of memory
   [ERROR] Tried to allocate 2.00 GiB
   ```
6. Click "Export" pentru a salva logs-urile
7. Analizează eroarea și rezolvă problema

### Exemplu 3: Monitorizare Federated Learning

**Scenariu**: Ai pornit o rundă FL și vrei să vezi ce se întâmplă

**Pași**:
1. Filtrează după Type: Federated Train
2. Filtrează după Status: Running
3. Vezi toate nodurile care participă
4. Click pe 👁️ pentru fiecare nod
5. Vezi progresul pe fiecare nod:
   ```
   [node1] Starting local training...
   [node1] Training:  50%|█████     | 22/44
   [node1] ✓ Training complete
   [node1] Computing delta...
   [node1] Pushing update to central...
   [node1] ✓ Update accepted
   ```

### Exemplu 4: Export Logs pentru Raport

**Scenariu**: Vrei să incluzi logs-uri într-un raport

**Pași**:
1. Găsește job-ul dorit
2. Click pe 👁️ (View Logs)
3. Click pe "Export" (💾)
4. Fișierul se descarcă: `job-fl_train_R-3-logs.txt`
5. Deschide fișierul în editor
6. Copiază logs-urile în raport

---

## 🔧 Troubleshooting

### Problema 1: Nu văd job-uri

**Cauză posibilă**: Filtrele sunt prea restrictive

**Soluție**:
1. Setează Status: All
2. Setează Type: All
3. Refresh pagina

### Problema 2: Auto-refresh nu funcționează

**Cauză posibilă**: Toggle-ul este dezactivat

**Soluție**:
1. Verifică că toggle-ul "Auto-refresh" este activat
2. Dacă nu, click pe el pentru a activa

### Problema 3: Live Stream nu afișează logs

**Cauză posibilă**: Job-ul nu este running sau nu are logs

**Soluție**:
1. Verifică că job-ul este Status: Running
2. Așteaptă câteva secunde pentru logs
3. Dacă tot nu apar, job-ul poate fi blocat

### Problema 4: Export nu funcționează

**Cauză posibilă**: Browser blochează download-ul

**Soluție**:
1. Verifică setările browser-ului
2. Permite download-uri de la localhost
3. Încearcă din nou

---

## 💡 Tips & Tricks

### Tip 1: Folosește Filtrele Eficient

Combină filtrele pentru a găsi rapid ce cauți:
```
Status: Running + Type: Federated Train
→ Vezi doar FL jobs active

Status: Failed + Type: Train
→ Vezi doar training-uri eșuate
```

### Tip 2: Monitorizează Multiple Job-uri

Deschide multiple tab-uri pentru a monitoriza mai multe job-uri simultan:
```
Tab 1: Node1 - FL job
Tab 2: Node2 - FL job
Tab 3: Node3 - FL job
```

### Tip 3: Pause pentru Citire

Când vezi multe logs rapid:
1. Click "Pause" pentru a opri streaming-ul
2. Citește logs-urile în liniște
3. Click "Resume" pentru a continua

### Tip 4: Clear pentru Curățenie

Când ecranul devine plin:
1. Click "Clear" pentru a șterge logs-urile vechi
2. Logs-urile noi vor continua să apară
3. Nu afectează logs-urile reale

### Tip 5: Export pentru Backup

Salvează logs-urile importante:
1. Export logs după fiecare training important
2. Păstrează-le pentru comparații
3. Folosește-le pentru debugging viitor

---

## 📚 Resurse Suplimentare

### Documentație
- **Backend API**: `OBSERVABILITY_FEATURE.md`
- **Frontend**: `services/node/ui/JOBS_FEATURE.md`
- **Implementare**: `JOBS_IMPLEMENTATION_SUMMARY.md`
- **Testare**: `OBSERVABILITY_TEST_RESULTS.md`

### API Endpoints
```bash
# List jobs
GET /api/jobs/list?status=running&job_type=federated_train&limit=50

# Get job status
GET /api/jobs/{job_id}/status

# Stream live logs (SSE)
GET /api/jobs/{job_id}/logs

# Get static logs
GET /api/jobs/{job_id}/logs/static?lines=100
```

### UI URLs
```
Node 1: http://localhost:3001/jobs
Node 2: http://localhost:3002/jobs
Node 3: http://localhost:3003/jobs
```

---

## ✅ Checklist Utilizare

### Înainte de a începe
- [ ] Serviciile sunt pornite (`docker compose ps`)
- [ ] API-urile răspund (`curl http://localhost:8001/api/health`)
- [ ] UI-urile sunt accesibile (http://localhost:3001)

### Pentru monitorizare
- [ ] Deschide pagina Jobs
- [ ] Activează Auto-refresh
- [ ] Filtrează după nevoie
- [ ] Click pe 👁️ pentru logs

### Pentru debugging
- [ ] Filtrează după Status: Failed
- [ ] Click pe 👁️ pentru job eșuat
- [ ] Citește logs-urile
- [ ] Export logs pentru analiză

### Pentru raportare
- [ ] Găsește job-urile relevante
- [ ] Export logs pentru fiecare
- [ ] Salvează fișierele
- [ ] Include în raport

---

## 🎉 Concluzie

Funcționalitatea de Observabilitate îți oferă **control complet** asupra job-urilor din sistem:
- ✅ Vezi tot ce se întâmplă
- ✅ Monitorizezi în timp real
- ✅ Debugging rapid și eficient
- ✅ Export pentru raportare

**Bucură-te de monitorizare completă!** 🚀

---

**Autor**: Fed-Med-FL Team  
**Versiune**: 1.0.0  
**Data**: 2026-04-23  
**Status**: ✅ Production Ready

