# Model Labels Feature (Updated)

**Data**: 2026-04-23  
**Versiune**: 0.2.2  
**Status**: ✅ Complete

---

## 📋 Overview

Implementare sistem nou de labels pentru modele în Model Registry. Înlocuiește vechiul sistem de "Type" cu un sistem flexibil de labels multiple.

**Update**: Eliminat label "archived" - modelele care nu mai sunt active revin la status "candidate".

---

## 🎯 Obiectiv

Permite identificarea clară a rolului fiecărui model prin labels:
- **active**: Modelul deployed (folosit pentru inference)
- **global**: Cel mai bun model (highest accuracy)
- **candidate**: Modele disponibile pentru promovare

Un model poate avea **1-2 labels** simultan (ex: "active" + "global" dacă cel mai bun model este și deployed).

**Important**: Orice model (inclusiv "global") poate fi promovat la "active".

---

## 🔧 Modificări Implementate

### 1. Database Schema (`services/node/api/app/database.py`)

**Adăugat coloană nouă:**
```python
class Model(Base):
    # ... existing fields ...
    labels = Column(JSON, nullable=True)  # ["global", "active", "candidate"]
```

**Migrare database:**
```sql
ALTER TABLE models ADD COLUMN labels TEXT;
```

### 2. Backend API (`services/node/api/app/main.py`)

**Funcție pentru calcularea labels:**
```python
def compute_model_labels(models_list, db: Session):
    """
    Compute labels for models based on accuracy and deployed status.
    
    Labels:
    - "active": deployed model (used for inference)
    - "global": best model (highest accuracy)
    - "candidate": neither active nor global (or both)
    
    A model can have 1-2 labels (e.g., both "global" and "active" if best model is deployed)
    Note: No "archived" label - old deployed models return to "candidate" status
    """
```

**Logica de calcul:**
1. Găsește modelul deployed → label "active"
2. Găsește modelul cu cea mai mare accuracy (include toate modelele) → label "global"
3. Dacă un model nu are niciun label → label "candidate"
4. Sincronizează `type` cu labels:
   - Dacă are label "active" → type = "deployed"
   - Altfel → type = "candidate"

**Endpoints modificate:**
- `GET /api/models/registry` - Calculează și returnează labels pentru toate modelele
- `GET /api/models/{model_id}` - Include labels în răspuns
- `POST /api/models/promote` - Promovează orice model (nu doar candidate), recalculează labels

**Logica de promovare (actualizată):**
```python
@app.post("/api/models/promote")
def promote_model(request, db):
    # Change current deployed model back to candidate (not archived!)
    current_deployed.type = "candidate"
    
    # Promote selected model
    model_to_promote.type = "deployed"
    
    # Recalculate labels for all models
    compute_model_labels(all_models, db)
```

### 3. API Schema (`services/node/api/app/schemas.py`)

**Actualizat ModelInfo:**
```python
class ModelInfo(BaseModel):
    model_id: str
    model_name: str
    version: str
    type: str  # Kept for backward compatibility
    labels: Optional[List[str]] = []  # NEW
    round_id: Optional[str]
    metrics: Optional[Dict[str, Any]]
    created_at: str
```

### 4. Frontend UI (`services/node/ui/src/app/models/page.tsx`)

**Modificări UI:**
- Coloană "Type" → "Labels"
- Display multiple chips pentru fiecare label
- Culori distinctive:
  - `active` → verde (success)
  - `global` → albastru (primary)
  - `candidate` → portocaliu (warning)

**Logica de promovare (actualizată):**
- Buton "Promote to Active" apare pentru ORICE model fără label "active"
- Include modele cu label "global"
- După promovare, labels sunt recalculate automat

**Legend actualizată:**
```
✅ active - Currently deployed model used for inference
🌍 global - Best model (highest accuracy)
⚠️ candidate - Models available for promotion

💡 A model can have multiple labels. For example, if the best model 
   is also deployed, it will have both "global" and "active" labels.
   Any model (including "global") can be promoted to "active".
```

---

## 📊 Exemple de Labels

### Exemplu 1: Model deployed care este și cel mai bun
```json
{
  "model_id": "resnet18_R-TEST-FIX-2_candidate",
  "type": "deployed",
  "labels": ["active", "global"],
  "metrics": {
    "accuracy": 0.9770114942528736
  }
}
```

### Exemplu 2: Model global (cel mai bun) dar nu deployed
```json
{
  "model_id": "resnet18_R-BEST_candidate",
  "type": "candidate",
  "labels": ["global"],
  "metrics": {
    "accuracy": 0.9770114942528736
  }
}
```

### Exemplu 3: Model candidat simplu
```json
{
  "model_id": "resnet18_R-2NODES-1776623349_candidate",
  "type": "candidate",
  "labels": ["candidate"],
  "metrics": {
    "accuracy": 0.9022988505747126
  }
}
```

---

## 🔄 Workflow de Promovare (Actualizat)

### Scenariul 1: Promovare model global

1. **Înainte de promovare:**
   - Model A (deployed): `["active"]` (accuracy: 0.93)
   - Model B (candidate): `["global"]` (accuracy: 0.97 - cel mai bun!)

2. **User promovează Model B (global):**
   ```bash
   POST /api/models/promote
   { "model_id": "model_B" }
   ```

3. **După promovare:**
   - Model A (candidate): `["candidate"]` (nu mai e activ, revine la candidate)
   - Model B (deployed): `["active", "global"]` (cel mai bun și activ!)

### Scenariul 2: Promovare model candidat

1. **Înainte de promovare:**
   - Model A (deployed): `["active", "global"]` (accuracy: 0.97)
   - Model C (candidate): `["candidate"]` (accuracy: 0.90)

2. **User promovează Model C:**
   ```bash
   POST /api/models/promote
   { "model_id": "model_C" }
   ```

3. **După promovare:**
   - Model A (candidate): `["global"]` (nu mai e activ, dar rămâne cel mai bun)
   - Model C (deployed): `["active"]` (activ dar nu cel mai bun)

---

## 🧪 Testing

### Test 1: Verificare labels în API
```bash
curl http://localhost:8001/api/models/registry | jq '.models[] | {model_id, labels, type, accuracy: .metrics.accuracy}'
```

### Test 2: Promovare model global
```bash
# Get global model ID
GLOBAL_ID=$(curl -s http://localhost:8001/api/models/registry | jq -r '.models[] | select(.labels[] == "global") | .model_id' | head -1)

echo "Promoting global model: $GLOBAL_ID"

# Promote it
curl -X POST http://localhost:8001/api/models/promote \
  -H "Content-Type: application/json" \
  -d "{\"model_id\": \"$GLOBAL_ID\"}"

# Verify it now has both labels
curl http://localhost:8001/api/models/registry | jq '.models[] | select(.model_id == "'$GLOBAL_ID'")'
```

**Expected output:**
```json
{
  "labels": ["active", "global"],
  "type": "deployed"
}
```

### Test 3: Verificare că vechiul activ devine candidate
```bash
# After promotion, check old active model
curl http://localhost:8001/api/models/registry | jq '.models[] | select(.labels == ["candidate"]) | {model_id, labels, type}'
```

---

## 🎨 UI Behavior

### Buton Promote
- **Apare pentru**: Orice model FĂRĂ label "active"
- **Include**: Modele cu labels "candidate", "global", sau "global + candidate"
- **Nu apare pentru**: Modele cu label "active" (deja deployed)

### După Promovare
- Modelul promovat primește label "active"
- Dacă e și cel mai bun, are labels ["active", "global"]
- Vechiul model activ pierde label "active" și devine "candidate" sau "global"

---

## 📈 Beneficii

1. **Simplitate**: Doar 3 labels (nu mai există "archived")
2. **Flexibilitate**: Orice model poate fi promovat, inclusiv "global"
3. **Claritate**: Labels multiple oferă mai multă informație
4. **Automatizare**: Labels calculate automat bazat pe accuracy și deployed status
5. **Reversibilitate**: Modelele pot fi promovate și "demovate" fără a fi arhivate

---

## 🚀 Deployment

```bash
# Build services
docker compose build node1-api node2-api node3-api node1-ui node2-ui node3-ui

# Restart services
docker compose up -d node1-api node2-api node3-api node1-ui node2-ui node3-ui

# Verify
curl http://localhost:8001/api/models/registry | jq '.models[0].labels'
```

---

## 📊 Metrici

- **Backend**: ~80 linii cod (compute_model_labels + promote logic)
- **Frontend**: ~30 linii modificate (labels display + promote button)
- **Database**: 1 coloană nouă (labels JSON)
- **API Schema**: 1 field nou (labels)

**Total**: ~110 linii modificate/adăugate

---

## ✅ Checklist Implementare

- [x] Adăugat coloană `labels` în database schema
- [x] Migrat database-uri existente (node1, node2, node3)
- [x] Implementat funcție `compute_model_labels()`
- [x] Eliminat logica de "archived" - modele revin la "candidate"
- [x] Sincronizat `type` cu labels pentru backward compatibility
- [x] Actualizat endpoint `/api/models/registry`
- [x] Actualizat endpoint `/api/models/{model_id}`
- [x] Actualizat endpoint `/api/models/promote` - permite promovare orice model
- [x] Actualizat schema `ModelInfo` cu field `labels`
- [x] Modificat UI pentru display labels multiple
- [x] Actualizat buton promote - apare pentru orice model fără "active"
- [x] Eliminat referințe la "archived" din UI
- [x] Actualizat legend în UI
- [x] Testat API cu curl
- [x] Testat promovare model global
- [x] Verificat că vechiul activ devine candidate
- [x] Documentație completă

---

**Status Final**: ✅ Feature complet implementat și testat

**Key Changes from v1**:
- ❌ Eliminat label "archived"
- ✅ Orice model poate fi promovat (inclusiv "global")
- ✅ Vechiul model activ revine la "candidate" (nu "archived")
- ✅ Type sincronizat automat cu labels

---

## 🔧 Modificări Implementate

### 1. Database Schema (`services/node/api/app/database.py`)

**Adăugat coloană nouă:**
```python
class Model(Base):
    # ... existing fields ...
    labels = Column(JSON, nullable=True)  # ["global", "active", "candidate"]
```

**Migrare database:**
```sql
ALTER TABLE models ADD COLUMN labels TEXT;
```

### 2. Backend API (`services/node/api/app/main.py`)

**Funcție nouă pentru calcularea labels:**
```python
def compute_model_labels(models_list, db: Session):
    """
    Compute labels for models based on accuracy and deployed status.
    
    Labels:
    - "active": deployed model (used for inference)
    - "global": best model (highest accuracy)
    - "candidate": neither active nor global
    
    A model can have 1-2 labels (e.g., both "global" and "active" if best model is deployed)
    """
```

**Logica de calcul:**
1. Găsește modelul deployed → label "active"
2. Găsește modelul cu cea mai mare accuracy (exclude archived) → label "global"
3. Dacă un model nu are niciun label → label "candidate"
4. Modelele archived → label "archived"

**Endpoints modificate:**
- `GET /api/models/registry` - Calculează și returnează labels pentru toate modelele
- `GET /api/models/{model_id}` - Include labels în răspuns
- `POST /api/models/promote` - Recalculează labels după promovare

### 3. API Schema (`services/node/api/app/schemas.py`)

**Actualizat ModelInfo:**
```python
class ModelInfo(BaseModel):
    model_id: str
    model_name: str
    version: str
    type: str  # Kept for backward compatibility
    labels: Optional[List[str]] = []  # NEW
    round_id: Optional[str]
    metrics: Optional[Dict[str, Any]]
    created_at: str
```

### 4. Frontend UI (`services/node/ui/src/app/models/page.tsx`)

**Modificări UI:**
- Coloană "Type" → "Labels"
- Display multiple chips pentru fiecare label
- Culori distinctive:
  - `active` → verde (success)
  - `global` → albastru (primary)
  - `candidate` → portocaliu (warning)
  - `archived` → gri (default)

**Logica de promovare:**
- Buton "Promote to Active" apare doar pentru modele cu label "candidate" (fără "active")
- După promovare, labels sunt recalculate automat

**Legend actualizată:**
```
✅ active - Currently deployed model used for inference
🌍 global - Best model (highest accuracy)
⚠️ candidate - Newly trained models awaiting promotion
📦 archived - Previous versions no longer in use

💡 A model can have multiple labels. For example, if the best model 
   is also deployed, it will have both "global" and "active" labels.
```

---

## 📊 Exemple de Labels

### Exemplu 1: Model deployed care este și cel mai bun
```json
{
  "model_id": "resnet18_R-TEST-FIX-2_candidate",
  "type": "deployed",
  "labels": ["active", "global"],
  "metrics": {
    "accuracy": 0.9770114942528736
  }
}
```

### Exemplu 2: Model candidat (nu deployed, nu cel mai bun)
```json
{
  "model_id": "resnet18_R-2NODES-1776623349_candidate",
  "type": "candidate",
  "labels": ["candidate"],
  "metrics": {
    "accuracy": 0.9022988505747126
  }
}
```

### Exemplu 3: Model arhivat
```json
{
  "model_id": "resnet18_R-SUCCESS-1_candidate",
  "type": "archived",
  "labels": ["archived"],
  "metrics": {
    "accuracy": 0.9770114942528736
  }
}
```

---

## 🔄 Workflow de Promovare

1. **Înainte de promovare:**
   - Model A (deployed): `["active", "global"]` (accuracy: 0.97)
   - Model B (candidate): `["candidate"]` (accuracy: 0.95)

2. **User promovează Model B:**
   ```bash
   POST /api/models/promote
   { "model_id": "model_B" }
   ```

3. **După promovare:**
   - Model A (archived): `["archived"]`
   - Model B (deployed): `["active"]` (nu "global" pentru că A are accuracy mai mare)

4. **Dacă Model B ar avea accuracy mai mare:**
   - Model B (deployed): `["active", "global"]`

---

## 🧪 Testing

### Test 1: Verificare labels în API
```bash
curl http://localhost:8001/api/models/registry | jq '.models[] | {model_id, labels, accuracy: .metrics.accuracy}'
```

### Test 2: Verificare model deployed
```bash
curl http://localhost:8001/api/models/registry | jq '.models[] | select(.type == "deployed")'
```

**Expected output:**
```json
{
  "labels": ["active", "global"],
  "type": "deployed"
}
```

### Test 3: Promovare model
```bash
# Get a candidate model ID
CANDIDATE_ID=$(curl -s http://localhost:8001/api/models/registry | jq -r '.models[] | select(.labels[] == "candidate") | .model_id' | head -1)

# Promote it
curl -X POST http://localhost:8001/api/models/promote \
  -H "Content-Type: application/json" \
  -d "{\"model_id\": \"$CANDIDATE_ID\"}"

# Verify labels updated
curl http://localhost:8001/api/models/registry | jq '.models[] | select(.model_id == "'$CANDIDATE_ID'")'
```

---

## 📝 Database Migration

Pentru noduri existente, coloana `labels` a fost adăugată astfel:

```bash
# Node 1
docker compose exec node1-api python3 -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('ALTER TABLE models ADD COLUMN labels TEXT')
conn.commit()
conn.close()
"

# Repeat for node2 and node3
```

Labels sunt calculate automat la primul request către `/api/models/registry`.

---

## 🎨 UI Screenshots

### Before (Type column):
```
| Model ID | Architecture | Type      |
|----------|--------------|-----------|
| model_1  | resnet18     | deployed  |
| model_2  | resnet18     | candidate |
```

### After (Labels column):
```
| Model ID | Architecture | Labels                    |
|----------|--------------|---------------------------|
| model_1  | resnet18     | [active] [global]        |
| model_2  | resnet18     | [candidate]              |
```

---

## 🔍 Backward Compatibility

- Coloana `type` este păstrată în database și API pentru backward compatibility
- Vechile endpoint-uri continuă să funcționeze
- Labels sunt calculate dinamic bazat pe `type` și `metrics.accuracy`

---

## 📈 Beneficii

1. **Claritate**: Labels multiple oferă mai multă informație decât un singur "type"
2. **Flexibilitate**: Un model poate avea mai multe roluri simultan
3. **Automatizare**: Labels sunt calculate automat, nu trebuie setate manual
4. **Vizibilitate**: UI-ul arată clar care model este cel mai bun și care este activ

---

## 🚀 Deployment

```bash
# Build services
docker compose build node1-api node2-api node3-api node1-ui node2-ui node3-ui

# Restart services
docker compose up -d node1-api node2-api node3-api node1-ui node2-ui node3-ui

# Verify
curl http://localhost:8001/api/models/registry | jq '.models[0].labels'
```

---

## 📊 Metrici

- **Backend**: ~60 linii cod nou (compute_model_labels function)
- **Frontend**: ~40 linii modificate (labels display)
- **Database**: 1 coloană nouă (labels JSON)
- **API Schema**: 1 field nou (labels)

**Total**: ~100 linii modificate/adăugate

---

## ✅ Checklist Implementare

- [x] Adăugat coloană `labels` în database schema
- [x] Migrat database-uri existente (node1, node2, node3)
- [x] Implementat funcție `compute_model_labels()`
- [x] Actualizat endpoint `/api/models/registry`
- [x] Actualizat endpoint `/api/models/{model_id}`
- [x] Actualizat endpoint `/api/models/promote`
- [x] Actualizat schema `ModelInfo` cu field `labels`
- [x] Modificat UI pentru display labels multiple
- [x] Actualizat legend în UI
- [x] Testat API cu curl
- [x] Testat UI în browser
- [x] Verificat promovare model
- [x] Documentație completă

---

**Status Final**: ✅ Feature complet implementat și testat

**Next Steps**: 
- Testare end-to-end cu training și promovare
- Verificare în scenarii de FL cu multiple runde
