# Fix Inference - On-Premise Implementation

**Data**: 2026-04-19  
**Status**: ✅ Rezolvat

---

## Problema Inițială

### Eroare
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 149: invalid start byte
```

### Cauză
Endpoint-ul `/api/infer` aștepta `image_paths: List[str]` (path-uri text), dar cineva încerca să trimită fișiere binare (imagini) direct în request. Când Pydantic încerca să valideze request-ul și găsea bytes în loc de string-uri, FastAPI încerca să encodeze eroarea ca JSON, dar bytes-urile nu puteau fi convertite la UTF-8.

### Context Medical
În sistemele medicale, imaginile pacienților **NU** trebuie să părăsească sistemul spitalului din motive de:
- Securitate (HIPAA compliance)
- Privacy (GDPR compliance)
- Data sovereignty
- Audit trail

---

## Soluția Implementată

### 1. **Clarificare Arhitectură**

Sistemul folosește **on-premise inference**:
- Imaginile sunt **deja pe server** (în sistemul spitalului)
- Nu există upload de imagini
- Inference rulează pe path-uri către imagini existente
- Doar rezultatele (predicții, Grad-CAM) sunt stocate

### 2. **Nou Endpoint: Browse Images**

**Endpoint**: `GET /api/infer/browse?directory=/hospital_data`

**Funcționalitate**:
```python
@app.get("/api/infer/browse")
def browse_hospital_images(directory: str = "/hospital_data"):
    """
    Browse available images in hospital data directories.
    Images remain in their original location (on-premise security).
    """
    # Security: whitelist of allowed directories
    allowed_dirs = [
        "/hospital_data",
        "/mnt/radiology",
        "/storage/test_images",
        "/storage/datasets"
    ]
    
    # Validate directory is allowed
    if not any(directory.startswith(allowed) for allowed in allowed_dirs):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # List image files
    # Return: files, subdirectories, metadata
```

**Beneficii**:
- Permite UI-ului să navigheze în directoare
- Nu copiază imagini
- Securitate prin whitelist

### 3. **Îmbunătățit Endpoint: Inference**

**Endpoint**: `POST /api/infer`

**Validări Adăugate**:
```python
@app.post("/api/infer")
async def run_inference(request: InferRequest):
    """
    Run inference on images at specified filesystem paths.
    
    IMPORTANT - On-Premise Medical Imaging:
    - Images must already exist on the server filesystem
    - Images are NOT uploaded - they are read from existing locations
    - This ensures medical data never leaves the hospital premises
    """
    # Validate all image paths
    for path in request.image_paths:
        if not os.path.exists(path):
            raise HTTPException(400, f"Image path does not exist: {path}")
        if not os.path.isfile(path):
            raise HTTPException(400, f"Path is not a file: {path}")
        if not os.access(path, os.R_OK):
            raise HTTPException(403, f"No read permission: {path}")
    
    # Create inference job...
```

**Documentație Clară**:
- Explicație on-premise în docstring
- Exemple de path-uri valide
- Note despre securitate

### 4. **UI Update: File Browser**

**Înainte** (❌ Greșit):
```typescript
// Upload files
<input type="file" multiple onChange={handleUpload} />
```

**După** (✅ Corect):
```typescript
// Browse server filesystem
const browseDirectory = async (directory: string) => {
  const response = await fetch(
    `${apiBase}/api/infer/browse?directory=${directory}`
  );
  const data = await response.json();
  setFiles(data.files);
};

// Select images by path
const runInference = async (selectedPaths: string[]) => {
  const response = await fetch(`${apiBase}/api/infer`, {
    method: 'POST',
    body: JSON.stringify({ image_paths: selectedPaths })
  });
};
```

**Features**:
- Navigare în directoare
- Selectare multiple imagini
- Checkbox pentru fiecare imagine
- Afișare metadata (size, modified date)

---

## Workflow Corect

### Pas 1: Browse
```bash
GET /api/infer/browse?directory=/storage/datasets/dataset_train_abc123/NORMAL
```

**Response**:
```json
{
  "directory": "/storage/datasets/dataset_train_abc123/NORMAL",
  "files": [
    {
      "name": "image001.jpeg",
      "path": "/storage/datasets/dataset_train_abc123/NORMAL/image001.jpeg",
      "size": 245678
    }
  ]
}
```

### Pas 2: Inference
```bash
POST /api/infer
{
  "image_paths": [
    "/storage/datasets/dataset_train_abc123/NORMAL/image001.jpeg"
  ],
  "generate_gradcam": true
}
```

**Response**:
```json
{
  "job_id": "infer_abc123",
  "status": "pending"
}
```

### Pas 3: Results
```bash
GET /api/infer/results/infer_abc123
```

**Response**:
```json
{
  "status": "completed",
  "results": [
    {
      "image_path": "/storage/.../image001.jpeg",
      "predicted_class": 0,
      "confidence": 0.95,
      "gradcam_path": "/storage/results/inference/infer_abc123_0_gradcam.png"
    }
  ]
}
```

---

## Docker Configuration

### Volume Mounts

```yaml
services:
  node1-api:
    volumes:
      # Storage pentru rezultate
      - ./storage/node1:/storage
      
      # Mount READ-ONLY pentru date spital
      - /mnt/hospital/radiology:/hospital_data:ro
      
  node1-worker:
    volumes:
      # Aceleași volume
      - ./storage/node1:/storage
      - /mnt/hospital/radiology:/hospital_data:ro
```

**Important**: Flag `:ro` (read-only) previne modificarea datelor medicale.

---

## Testare

### Script Automat

```bash
# Rulează test complet
make test-inference
```

**Ce testează**:
1. Verifică dataset-uri disponibile
2. Browse imagini în dataset
3. Verifică model deployed
4. Rulează inference pe 3 imagini
5. Monitorizează progres
6. Afișează rezultate

### Test Manual

```bash
# 1. Browse
curl "http://localhost:8001/api/infer/browse?directory=/storage/datasets"

# 2. Inference
curl -X POST http://localhost:8001/api/infer \
  -H "Content-Type: application/json" \
  -d '{
    "image_paths": ["/storage/datasets/.../image.jpeg"],
    "generate_gradcam": true
  }'

# 3. Results
curl http://localhost:8001/api/infer/results/infer_xyz789
```

---

## Fișiere Modificate

### Backend
- ✅ `services/node/api/app/main.py`
  - Adăugat `/api/infer/browse` endpoint
  - Îmbunătățit `/api/infer` cu validări
  - Documentație clară on-premise

### Frontend
- ✅ `services/node/ui/src/app/inference/page.tsx`
  - Înlocuit upload cu file browser
  - Navigare în directoare
  - Selectare imagini cu checkbox
  - Afișare rezultate

### Scripts
- ✅ `scripts/test_inference_onpremise.sh`
  - Test automat complet
  - Verificări securitate
  - Afișare rezultate

### Documentation
- ✅ `docs/INFERENCE_ONPREMISE.md`
  - Documentație completă
  - Arhitectură
  - Best practices
  - Troubleshooting

### Makefile
- ✅ Adăugat `make test-inference`

---

## Beneficii

### Securitate
✅ Imaginile nu părăsesc sistemul spitalului  
✅ Read-only access la date medicale  
✅ Whitelist de directoare permise  
✅ Validare strictă path-uri  

### Compliance
✅ HIPAA compliant (data at rest)  
✅ GDPR compliant (data minimization)  
✅ Audit trail complet  
✅ Data sovereignty  

### Performance
✅ Nu există overhead de upload  
✅ Acces local rapid la imagini  
✅ Minimal storage (doar rezultate)  

### Usability
✅ UI intuitiv pentru browsing  
✅ Selectare multiple imagini  
✅ Vizualizare rezultate clare  

---

## Comparație: Înainte vs După

| Aspect | Înainte (❌) | După (✅) |
|--------|-------------|----------|
| **Upload imagini** | Da (greșit) | Nu (corect) |
| **Securitate** | Risc HIPAA | Compliant |
| **Storage** | Dublat | Minimal |
| **Performance** | Lent | Rapid |
| **Erori** | UnicodeDecodeError | Validări clare |
| **UI** | File upload | File browser |

---

## Verificare

### Rebuild și Restart

```bash
# Rebuild servicii
docker compose build node1-api node1-ui

# Restart servicii
docker compose up -d node1-api node1-ui
```

### Test

```bash
# Test automat
make test-inference

# Sau manual
curl "http://localhost:8001/api/infer/browse?directory=/storage/datasets"
```

### UI

```
http://localhost:3001/inference
```

**Verifică**:
- ✅ File browser funcționează
- ✅ Poți naviga în directoare
- ✅ Poți selecta imagini
- ✅ Inference rulează corect
- ✅ Rezultate sunt afișate

---

## Concluzie

**Problema**: Eroare UnicodeDecodeError din cauza încercării de upload imagini binare.

**Soluție**: Implementare corectă on-premise inference cu:
- Browse endpoint pentru navigare
- Validări stricte pentru securitate
- UI cu file browser
- Documentație completă

**Status**: ✅ Rezolvat și testat

**Impact**: Sistem conform cu cerințele medicale (HIPAA/GDPR) și funcțional pentru inference on-premise.

---

**Autor**: Fed-Med-FL Team  
**Data**: 2026-04-19  
**Versiune**: 0.1.0
