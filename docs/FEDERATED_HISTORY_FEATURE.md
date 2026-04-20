# Federated Learning - Istoric Runde de Antrenare

**Data**: 2026-04-20  
**Status**: ✅ Implementat

---

## Modificări Implementate

### 1. Nou Endpoint API - Istoric Runde FL

**Endpoint**: `GET /api/federated/history`

**Locație**: `services/node/api/app/main.py`

**Funcționalitate**:
- Returnează istoricul complet al rundelor de federated learning pentru nodul curent
- Sortează rundele cu cele active primele, apoi după data creării (descrescător)
- Include informații despre:
  - Status local (completed, running, failed, pending)
  - Status central (aggregated, training, collecting)
  - Metrici de training (accuracy, F1, precision, recall, AUC)
  - Model ID și tip (candidate, deployed, archived)
  - Timestamp-uri (created_at, completed_at)

**Exemplu Response**:
```json
{
  "total_rounds": 21,
  "rounds": [
    {
      "round_id": "R-2NODES-ROUND2-1776624059",
      "is_active": false,
      "local_status": "completed",
      "job_id": "fl_train_R-2NODES-ROUND2-1776624059_c116d7ec",
      "created_at": "2026-04-19T18:41:00.589204",
      "completed_at": "2026-04-19T18:43:33.570877",
      "model_id": "resnet18_R-2NODES-ROUND2-1776624059_candidate",
      "model_type": "archived",
      "metrics": {
        "accuracy": 0.7931034482758621,
        "f1": 0.8481012658227848,
        "auc": 0.8982922201138519
      },
      "central_status": null
    }
  ]
}
```

---

### 2. UI Îmbunătățit - Pagina Federated Learning

**Locație**: `services/node/ui/src/app/federated/page.tsx`

**Funcționalități Noi**:

#### Tabel Istoric Runde
- ✅ Afișează toate rundele de training în ordine cronologică inversă
- ✅ Rundele active sunt evidențiate (background diferit + badge "ACTIVE")
- ✅ Rundele active apar primele în listă
- ✅ Iconiță specială pentru rundele active (RadioButtonChecked)

#### Coloane Tabel
1. **Round ID**: 
   - Font monospace pentru lizibilitate
   - Bold pentru rundele active

2. **Model**: 
   - Numele modelului (ex: resnet18)
   - Tip model (candidate/deployed/archived) ca badge outlined

3. **Status**: 
   - Iconiță + Badge "ACTIVE" pentru rundele active (albastru)
   - Chip colorat cu statusul central pentru rundele finalizate
   - Verde pentru "aggregated"
   - Gri pentru "completed"

4. **Joined**: 
   - Iconiță CheckCircle (verde) + Chip cu status local dacă a participat
   - Chip "Not Joined" (gri) dacă nu a participat
   - Status local: completed, running, failed, pending

5. **Metrics**: 
   - Accuracy (%)
   - F1 Score (%)
   - AUC (%)
   - Formatare la 1 zecimală

6. **Actions**: 
   - Buton "Join Round" (albastru, contained) - doar pentru rundele active la care nu s-a alăturat
   - Buton "View Details" (outlined) - pentru toate celelalte runde

#### Features Adiționale
- ✅ **Auto-refresh**: Istoricul se actualizează automat la fiecare 10 secunde
- ✅ **Manual refresh**: Buton "Refresh History" în header
- ✅ **Loading indicator**: CircularProgress când se încarcă datele
- ✅ **Empty state**: Mesaj informativ când nu există runde
- ✅ **Quick join**: Buton "Join Round" direct în tabel pentru rundele active
- ✅ **Join status**: Indicator vizual dacă nodul a participat la rundă
- ✅ **Click to view**: Click pe "View Details" pentru a vedea detaliile rundei

---

## Logica de Sortare

Rundele sunt sortate după următoarea prioritate:

1. **Runde active** (is_active=true) - apar primele
2. **Data creării** (created_at) - descrescător (cele mai recente primele)

```python
rounds_history.sort(key=lambda x: (not x["is_active"], x["created_at"] or ""), reverse=True)
```

**Exemplu**:
```
1. R-ACTIVE-1 (is_active=true, created_at=2026-04-20)  ← ACTIVE, apare prima
2. R-RECENT-1 (is_active=false, created_at=2026-04-19) ← Cea mai recentă finalizată
3. R-OLD-1 (is_active=false, created_at=2026-04-18)    ← Mai veche
```

---

## Determinarea Rundelor Active

O rundă este considerată **activă** dacă:
- Central server returnează status pentru rundă
- Status-ul central este unul din: `["created", "training", "collecting"]`

```python
is_active = False
if central_status:
    central_round_status = central_status.get("status", "")
    is_active = central_round_status in ["created", "training", "collecting"]
```

---

## Determinarea Participării la Rundă

Un nod este considerat că **a participat** la o rundă dacă:
- Status local nu este "not_started"
- Există un job_id asociat rundei

```typescript
const hasJoined = round.local_status !== 'not_started' && round.job_id !== null;
```

**Cazuri**:
- ✅ **Joined**: Nodul a făcut join și are un job de training (completed, running, failed, pending)
- ❌ **Not Joined**: Nodul nu a participat la rundă (local_status = "not_started" sau job_id = null)

---

## Stilizare UI

### Rundă Activă
```tsx
<TableRow
  sx={{
    backgroundColor: round.is_active ? 'action.hover' : 'inherit',
    '&:hover': { backgroundColor: 'action.selected' },
  }}
>
```

### Status Badge
```tsx
{round.is_active ? (
  <>
    <ActiveIcon color="primary" fontSize="small" />
    <Chip label="ACTIVE" color="primary" size="small" />
  </>
) : (
  <Chip
    label={round.central_status?.status || 'completed'}
    size="small"
    color={round.central_status?.status === 'aggregated' ? 'success' : 'default'}
  />
)}
```

### Joined Indicator
```tsx
{hasJoined ? (
  <>
    <CheckCircleIcon color="success" fontSize="small" />
    <Chip label={round.local_status} size="small" color={getStatusColor(round.local_status)} />
  </>
) : (
  <Chip label="Not Joined" size="small" color="default" />
)}
```

### Action Button
```tsx
{round.is_active && !hasJoined ? (
  <Button
    size="small"
    variant="contained"
    color="primary"
    startIcon={<HubIcon />}
    onClick={() => {
      setRoundId(round.round_id);
      handleJoinRound();
    }}
  >
    Join Round
  </Button>
) : (
  <Button
    size="small"
    variant="outlined"
    onClick={() => handleSelectRound(round)}
  >
    View Details
  </Button>
)}
```

---

## Testare

### Test Endpoint
```bash
curl -s http://localhost:8001/api/federated/history | python3 -m json.tool
```

### Test UI
1. Deschide http://localhost:3001/federated
2. Verifică că tabelul "Training Rounds History" apare
3. Verifică că rundele sunt sortate corect (active primele)
4. Verifică că badge-ul "ACTIVE" apare pentru rundele active
5. Click pe "View Details" pentru o rundă

---

## Deployment

### Rebuild Servicii
```bash
# Rebuild API-uri
docker compose build node1-api node2-api node3-api

# Rebuild UI-uri
docker compose build node1-ui node2-ui node3-ui

# Restart servicii
docker compose up -d node1-api node2-api node3-api node1-ui node2-ui node3-ui
```

### Verificare
```bash
# Verifică că serviciile rulează
docker compose ps

# Verifică logs
docker compose logs node1-api --tail 20
docker compose logs node1-ui --tail 20

# Test endpoint
curl http://localhost:8001/api/federated/history
```

---

## Beneficii

### Pentru Utilizatori
✅ **Vizibilitate completă**: Vezi toate rundele de training într-un singur loc  
✅ **Identificare rapidă**: Rundele active sunt evidențiate clar  
✅ **Informații detaliate**: Metrici, status, modele - totul într-un tabel  
✅ **Navigare ușoară**: Click pe "View Details" pentru detalii complete  
✅ **Auto-refresh**: Datele se actualizează automat  

### Pentru Dezvoltatori
✅ **Endpoint reutilizabil**: Poate fi folosit și de alte componente  
✅ **Sortare inteligentă**: Logică clară pentru prioritizarea rundelor  
✅ **Performanță**: Caching la nivel de browser (10s refresh)  
✅ **Extensibil**: Ușor de adăugat filtre sau sortări suplimentare  

---

## Îmbunătățiri Viitoare (Opțional)

### Filtrare și Căutare
- [ ] Filtru după status (completed, running, failed)
- [ ] Căutare după Round ID
- [ ] Filtru după interval de date

### Vizualizare
- [ ] Grafic cu evoluția metricilor pe runde
- [ ] Timeline vizual pentru rundele FL
- [ ] Comparație între runde (side-by-side)

### Export
- [ ] Export istoric ca CSV
- [ ] Export metrici pentru analiză
- [ ] Raport PDF cu rezultatele rundelor

### Notificări
- [ ] Notificare când o rundă devine activă
- [ ] Notificare când training-ul se completează
- [ ] Alert pentru rundele failed

---

## Fișiere Modificate

1. **services/node/api/app/main.py**
   - Adăugat endpoint `GET /api/federated/history`
   - ~100 linii cod nou

2. **services/node/ui/src/app/federated/page.tsx**
   - Adăugat tabel istoric runde
   - Adăugat logică sortare și evidențiere runde active
   - ~200 linii cod nou

---

## Resurse

### API Documentation
- Endpoint: http://localhost:8001/docs#/default/get_federated_history_api_federated_history_get

### UI Access
- Node 1: http://localhost:3001/federated
- Node 2: http://localhost:3002/federated
- Node 3: http://localhost:3003/federated

---

**Autor**: Fed-Med-FL Team  
**Versiune**: 0.1.0  
**Status**: ✅ Production Ready
