# Actualizare Tabel Istoric Federated Learning

**Data**: 2026-04-20  
**Status**: ✅ Implementat

---

## Modificări Implementate

### Structură Nouă Tabel

Tabelul de istoric a fost restructurat pentru a avea următoarele coloane:

| Coloană | Descriere | Detalii |
|---------|-----------|---------|
| **Round ID** | Identificator rundă | Font monospace, bold pentru rundele active |
| **Model** | Model folosit | Nume model (ex: resnet18) + tip (candidate/deployed/archived) |
| **Status** | Status rundă | ACTIVE (iconiță + badge albastru) sau status central (aggregated/completed) |
| **Joined** | Participare nod | CheckCircle verde + status local SAU "Not Joined" |
| **Metrics** | Metrici relevante | Accuracy, F1, AUC (%) |
| **Actions** | Acțiuni disponibile | "Join Round" (doar pentru runde active) SAU "View Details" |

---

## Logică Implementată

### 1. Determinarea Participării (Joined)

```typescript
const hasJoined = round.local_status !== 'not_started' && round.job_id !== null;
```

**Cazuri**:
- ✅ **Joined**: Nodul are un job de training (completed, running, failed, pending)
- ❌ **Not Joined**: Nodul nu a participat (local_status = "not_started" sau job_id = null)

### 2. Afișare Status

**Pentru runde active**:
```tsx
<ActiveIcon color="primary" fontSize="small" />
<Chip label="ACTIVE" color="primary" size="small" />
```

**Pentru runde finalizate**:
```tsx
<Chip 
  label={round.central_status?.status || 'completed'} 
  size="small" 
  color={round.central_status?.status === 'aggregated' ? 'success' : 'default'}
/>
```

### 3. Afișare Joined Status

**Dacă a participat**:
```tsx
<CheckCircleIcon color="success" fontSize="small" />
<Chip 
  label={round.local_status} 
  size="small" 
  color={getStatusColor(round.local_status)}
/>
```

**Dacă nu a participat**:
```tsx
<Chip label="Not Joined" size="small" color="default" />
```

### 4. Buton Actions

**Pentru runde active la care nu s-a alăturat**:
```tsx
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
```

**Pentru toate celelalte runde**:
```tsx
<Button
  size="small"
  variant="outlined"
  onClick={() => handleSelectRound(round)}
>
  View Details
</Button>
```

---

## Exemple Vizuale

### Rundă Activă (Nu s-a alăturat)

| Round ID | Model | Status | Joined | Metrics | Actions |
|----------|-------|--------|--------|---------|---------|
| **R-ACTIVE-1** | resnet18<br/>candidate | 🔵 **ACTIVE** | Not Joined | - | **[Join Round]** |

### Rundă Activă (S-a alăturat, în curs)

| Round ID | Model | Status | Joined | Metrics | Actions |
|----------|-------|--------|--------|---------|---------|
| **R-ACTIVE-2** | resnet18<br/>candidate | 🔵 **ACTIVE** | ✅ running | Acc: 85.2%<br/>F1: 87.1% | [View Details] |

### Rundă Completată (S-a alăturat)

| Round ID | Model | Status | Joined | Metrics | Actions |
|----------|-------|--------|--------|---------|---------|
| R-COMPLETED-1 | resnet18<br/>deployed | aggregated | ✅ completed | Acc: 92.5%<br/>F1: 91.3%<br/>AUC: 95.8% | [View Details] |

### Rundă Completată (Nu s-a alăturat)

| Round ID | Model | Status | Joined | Metrics | Actions |
|----------|-------|--------|--------|---------|---------|
| R-COMPLETED-2 | resnet18<br/>candidate | aggregated | Not Joined | - | [View Details] |

---

## Culori și Iconițe

### Status Runde
- 🔵 **ACTIVE**: Albastru (primary) - rundă în curs
- ✅ **aggregated**: Verde (success) - rundă completată cu succes
- ⚪ **completed**: Gri (default) - rundă finalizată

### Joined Status
- ✅ **CheckCircle** (verde): Nodul a participat
- **completed**: Verde (success)
- **running**: Albastru (primary)
- **failed**: Roșu (error)
- **pending**: Portocaliu (warning)
- **Not Joined**: Gri (default)

### Butoane
- **Join Round**: Albastru contained (primary) - acțiune principală
- **View Details**: Outlined - acțiune secundară

---

## Beneficii Noi

### Pentru Utilizatori
✅ **Vizibilitate clară**: Vezi imediat la ce runde ai participat  
✅ **Join rapid**: Buton direct în tabel pentru runde active  
✅ **Status vizual**: Iconițe și culori pentru identificare rapidă  
✅ **Informații relevante**: Doar coloanele importante  
✅ **Acțiuni contextuale**: Butonul potrivit pentru fiecare situație  

### Pentru Workflow
✅ **Eficiență**: Join la rundă în 1 click din tabel  
✅ **Claritate**: Status-ul participării este evident  
✅ **Flexibilitate**: View Details pentru informații complete  

---

## Cazuri de Utilizare

### Caz 1: Rundă Nouă Activă
**Situație**: Central creează R-NEW-1, nodul nu s-a alăturat încă

**Afișare**:
- Status: 🔵 ACTIVE
- Joined: Not Joined
- Actions: **[Join Round]** (albastru)

**Acțiune**: Click pe "Join Round" → nodul se alătură automat

---

### Caz 2: Rundă Activă, Training în Curs
**Situație**: Nodul s-a alăturat și antrenează

**Afișare**:
- Status: 🔵 ACTIVE
- Joined: ✅ running (albastru)
- Metrics: Acc: 85.2%, F1: 87.1%
- Actions: [View Details]

**Acțiune**: Click pe "View Details" → vezi progresul detaliat

---

### Caz 3: Rundă Completată cu Succes
**Situație**: Training finalizat, model agregat

**Afișare**:
- Status: aggregated (verde)
- Joined: ✅ completed (verde)
- Metrics: Acc: 92.5%, F1: 91.3%, AUC: 95.8%
- Actions: [View Details]

**Acțiune**: Click pe "View Details" → vezi rezultatele complete

---

### Caz 4: Rundă la Care Nu S-a Participat
**Situație**: Rundă finalizată, nodul nu a participat

**Afișare**:
- Status: aggregated (verde)
- Joined: Not Joined (gri)
- Metrics: - (nu există)
- Actions: [View Details]

**Acțiune**: Click pe "View Details" → vezi informații generale despre rundă

---

## Deployment

### Rebuild și Restart
```bash
# Rebuild UI-uri
docker compose build node1-ui node2-ui node3-ui

# Restart UI-uri
docker compose up -d node1-ui node2-ui node3-ui
```

### Verificare
```bash
# Verifică că serviciile rulează
docker compose ps | grep ui

# Accesează UI
# Node 1: http://localhost:3001/federated
# Node 2: http://localhost:3002/federated
# Node 3: http://localhost:3003/federated
```

---

## Fișiere Modificate

1. **services/node/ui/src/app/federated/page.tsx**
   - Restructurat tabel cu noile coloane
   - Adăugat logică pentru "hasJoined"
   - Adăugat buton "Join Round" condiționat
   - Adăugat iconițe CheckCircle și ActiveIcon
   - ~150 linii modificate

2. **docs/FEDERATED_HISTORY_FEATURE.md**
   - Actualizat documentația cu noile coloane
   - Adăugat secțiune despre logica "Joined"
   - Adăugat exemple de stilizare

---

## Comparație: Înainte vs După

### Înainte
| Coloane | 7 coloane |
|---------|-----------|
| Round ID | Status | Local Status | Model | Metrics | Created | Actions |

**Probleme**:
- ❌ Prea multe coloane
- ❌ Nu se vede clar dacă ai participat
- ❌ Nu poți face join direct din tabel
- ❌ Coloana "Created" ocupă spațiu inutil

### După
| Coloane | 6 coloane |
|---------|-----------|
| Round ID | Model | Status | Joined | Metrics | Actions |

**Îmbunătățiri**:
- ✅ Coloane mai relevante
- ✅ Status participare clar (Joined)
- ✅ Join rapid din tabel
- ✅ Acțiuni contextuale (Join sau View)
- ✅ Mai compact și lizibil

---

## Testare

### Scenarii de Test

1. **Rundă activă, nu s-a alăturat**
   - Verifică: Badge "ACTIVE", "Not Joined", buton "Join Round"
   - Acțiune: Click "Join Round" → verifică că se alătură

2. **Rundă activă, training în curs**
   - Verifică: Badge "ACTIVE", CheckCircle + "running", buton "View Details"
   - Acțiune: Click "View Details" → vezi progresul

3. **Rundă completată, s-a alăturat**
   - Verifică: Status "aggregated", CheckCircle + "completed", metrici afișate
   - Acțiune: Click "View Details" → vezi rezultatele

4. **Rundă completată, nu s-a alăturat**
   - Verifică: Status "aggregated", "Not Joined", metrici lipsă
   - Acțiune: Click "View Details" → vezi info generale

---

## Concluzie

Tabelul de istoric a fost simplificat și îmbunătățit pentru a oferi:
- ✅ Informații mai relevante
- ✅ Acțiuni mai rapide (join direct)
- ✅ Vizibilitate clară a participării
- ✅ UI mai curat și intuitiv

**Status**: ✅ Gata pentru utilizare  
**Versiune**: 0.2.0  
**Data**: 2026-04-20

---

**Autor**: Fed-Med-FL Team
