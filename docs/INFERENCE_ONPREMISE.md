# On-Premise Inference - Medical Imaging Security

**Data**: 2026-04-19  
**Status**: ✅ Implementat

---

## Overview

Sistemul Fed-Med-FL implementează inference **on-premise** pentru a respecta cerințele de securitate medicală. Imaginile pacienților **NU** părăsesc niciodată sistemul spitalului.

## Principii de Securitate

### 1. **Data Sovereignty**
- Imaginile medicale rămân în sistemul spitalului
- Doar rezultatele inference (predicții, Grad-CAM) sunt stocate
- Nu există upload de imagini către server

### 2. **Read-Only Access**
- Containerele Docker au acces **read-only** la datele spitalului
- Volume mounts configurate cu flag `:ro`
- Previne modificarea accidentală a datelor medicale

### 3. **Path-Based Access**
- Inference folosește path-uri către imagini existente
- Validare strictă a path-urilor (whitelist de directoare)
- Verificare permisiuni de citire

---

## Arhitectură

```
┌─────────────────────────────────────────────────────────────┐
│              Sistemul Spitalului (On-Premise)                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  PACS / Medical Imaging System                       │   │
│  │  /mnt/hospital/radiology/                            │   │
│  │    ├── studies/                                      │   │
│  │    │   ├── patient_001/chest_xray.dcm                │   │
│  │    │   └── patient_002/chest_xray.dcm                │   │
│  │    └── ...                                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           │ (read-only mount)                │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Fed-Med-FL Node (Docker)                            │   │
│  │                                                       │   │
│  │  Volumes:                                            │   │
│  │  - /mnt/hospital/radiology:/hospital_data:ro        │   │
│  │  - ./storage/node1:/storage                         │   │
│  │                                                       │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ API + Worker                                │    │   │
│  │  │  • Citește imagini din /hospital_data       │    │   │
│  │  │  • Rulează inference local                  │    │   │
│  │  │  • Salvează DOAR rezultate în /storage      │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow Inference

### Pas 1: Browse Images

**Endpoint**: `GET /api/infer/browse?directory=/hospital_data/studies`

**Funcționalitate**:
- Listează imagini disponibile în directoare permise
- Returnează metadata (nume, size, data modificării)
- Suportă navigare în subdirectoare

**Securitate**:
- Whitelist de directoare permise
- Verificare permisiuni de citire
- Previne directory traversal attacks

**Exemplu Request**:
```bash
curl "http://localhost:8001/api/infer/browse?directory=/hospital_data/studies"
```

**Exemplu Response**:
```json
{
  "directory": "/hospital_data/studies",
  "subdirectories": [
    {
      "name": "patient_001",
      "path": "/hospital_data/studies/patient_001",
      "type": "directory"
    }
  ],
  "files": [
    {
      "name": "chest_xray.jpg",
      "path": "/hospital_data/studies/chest_xray.jpg",
      "size": 245678,
      "type": "file",
      "extension": ".jpg",
      "modified": "2026-04-19T10:30:00"
    }
  ],
  "total_files": 1,
  "total_subdirs": 1
}
```

---

### Pas 2: Run Inference

**Endpoint**: `POST /api/infer`

**Request Body**:
```json
{
  "image_paths": [
    "/hospital_data/studies/patient_001/chest_xray.jpg",
    "/hospital_data/studies/patient_002/chest_xray.jpg"
  ],
  "model_id": null,
  "generate_gradcam": true
}
```

**Validări**:
- ✅ Path-urile există pe filesystem
- ✅ Path-urile sunt fișiere (nu directoare)
- ✅ Permisiuni de citire sunt disponibile
- ✅ Path-urile sunt în directoare permise

**Response**:
```json
{
  "job_id": "infer_abc12345",
  "task_id": "celery-task-id",
  "status": "pending"
}
```

---

### Pas 3: Get Results

**Endpoint**: `GET /api/infer/results/{job_id}`

**Response**:
```json
{
  "job_id": "infer_abc12345",
  "status": "completed",
  "results": [
    {
      "result_id": "res_001",
      "image_path": "/hospital_data/studies/patient_001/chest_xray.jpg",
      "predicted_class": 1,
      "confidence": 0.95,
      "probabilities": [0.05, 0.95],
      "gradcam_path": "/storage/results/inference/infer_abc12345_0_gradcam.png"
    }
  ]
}
```

**Note**:
- `image_path`: Path original (nu este copiat)
- `gradcam_path`: Doar vizualizarea este salvată în `/storage`
- Imaginea originală rămâne neatinsă

---

## Docker Configuration

### docker-compose.yml

```yaml
services:
  node1-api:
    volumes:
      # Storage local pentru rezultate
      - ./storage/node1:/storage
      
      # Mount READ-ONLY pentru date spital
      - /mnt/hospital/radiology:/hospital_data:ro
      
      # Sau pentru testare
      - ./test_data:/hospital_data:ro
    
  node1-worker:
    volumes:
      # Aceleași volume ca API
      - ./storage/node1:/storage
      - /mnt/hospital/radiology:/hospital_data:ro
```

**Important**: Flag-ul `:ro` (read-only) previne modificarea datelor medicale.

---

## UI Implementation

### File Browser Component

UI-ul permite:
1. **Navigare** în directoare permise
2. **Selectare** imagini pentru inference
3. **Vizualizare** rezultate

**Nu există**:
- ❌ Upload de fișiere
- ❌ Copiere imagini
- ❌ Transfer de date

### Exemplu Cod (React)

```typescript
// Browse directory
const browseDirectory = async (directory: string) => {
  const response = await fetch(
    `${apiBase}/api/infer/browse?directory=${encodeURIComponent(directory)}`
  );
  const data = await response.json();
  setFiles(data.files);
};

// Run inference
const runInference = async (selectedPaths: string[]) => {
  const response = await fetch(`${apiBase}/api/infer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_paths: selectedPaths,
      generate_gradcam: true
    })
  });
  const data = await response.json();
  // Poll for results...
};
```

---

## Testare

### Test Automat

```bash
# Rulează test complet on-premise inference
make test-inference
```

**Ce testează**:
1. ✅ Verifică dataset-uri disponibile
2. ✅ Browse imagini în dataset
3. ✅ Verifică model deployed
4. ✅ Rulează inference pe 3 imagini
5. ✅ Monitorizează progres
6. ✅ Afișează rezultate

### Test Manual

```bash
# 1. Browse imagini
curl "http://localhost:8001/api/infer/browse?directory=/storage/datasets"

# 2. Selectează path-uri din response

# 3. Rulează inference
curl -X POST http://localhost:8001/api/infer \
  -H "Content-Type: application/json" \
  -d '{
    "image_paths": [
      "/storage/datasets/dataset_train_abc123/NORMAL/image001.jpeg"
    ],
    "generate_gradcam": true
  }'

# 4. Get results
curl http://localhost:8001/api/infer/results/infer_xyz789
```

---

## Directoare Permise

### Default Whitelist

```python
allowed_dirs = [
    "/hospital_data",           # Mount pentru PACS
    "/mnt/radiology",           # Mount alternativ
    "/storage/test_images",     # Imagini de test
    "/storage/datasets"         # Dataset-uri uploadate
]
```

### Adăugare Directoare Noi

**În `services/node/api/app/main.py`**:

```python
@app.get("/api/infer/browse")
def browse_hospital_images(directory: str = "/hospital_data"):
    allowed_dirs = [
        "/hospital_data",
        "/mnt/radiology",
        "/your/new/directory",  # Adaugă aici
        os.path.join(settings.STORAGE_ROOT, "test_images")
    ]
    # ...
```

---

## Securitate și Compliance

### HIPAA Compliance

✅ **Data at Rest**: Imaginile rămân în sistemul spitalului  
✅ **Access Control**: Whitelist de directoare + verificare permisiuni  
✅ **Audit Trail**: Toate operațiile sunt logate  
✅ **Minimal Data**: Doar rezultatele sunt stocate, nu imaginile  

### GDPR Compliance

✅ **Data Minimization**: Nu se copiază date personale  
✅ **Purpose Limitation**: Acces doar pentru inference  
✅ **Storage Limitation**: Rezultatele pot fi șterse automat  
✅ **Data Sovereignty**: Datele nu părăsesc jurisdicția  

---

## Troubleshooting

### Eroare: "Image path does not exist"

**Cauză**: Path-ul specificat nu există pe filesystem.

**Soluție**:
1. Verifică că volume mount-ul este corect în docker-compose.yml
2. Verifică că path-ul este absolut și corect
3. Folosește `/api/infer/browse` pentru a găsi path-uri valide

### Eroare: "No read permission for path"

**Cauză**: Containerul Docker nu are permisiuni de citire.

**Soluție**:
```bash
# Verifică permisiuni
ls -la /mnt/hospital/radiology

# Acordă permisiuni de citire
chmod -R +r /mnt/hospital/radiology

# Sau schimbă owner-ul
chown -R 1000:1000 /mnt/hospital/radiology
```

### Eroare: "Access to directory is not allowed"

**Cauză**: Directorul nu este în whitelist.

**Soluție**: Adaugă directorul în `allowed_dirs` (vezi secțiunea de mai sus).

---

## Best Practices

### 1. **Volume Mounts**
- Folosește întotdeauna `:ro` pentru date medicale
- Mount-ează doar directoarele necesare
- Evită mount-uri la root (`/`)

### 2. **Path Validation**
- Validează toate path-urile înainte de utilizare
- Folosește whitelist, nu blacklist
- Verifică permisiuni explicit

### 3. **Logging**
- Loghează toate accesele la imagini
- Include user ID, timestamp, path
- Păstrează logs pentru audit

### 4. **Cleanup**
- Șterge rezultatele vechi automat
- Păstrează doar metadata necesară
- Respectă politicile de retenție

---

## Comparație: Upload vs On-Premise

| Aspect | Upload (❌ Greșit) | On-Premise (✅ Corect) |
|--------|-------------------|----------------------|
| **Securitate** | Imagini copiate pe server | Imagini rămân în locația originală |
| **Compliance** | Risc HIPAA/GDPR | Conform HIPAA/GDPR |
| **Storage** | Dublează spațiul necesar | Minimal (doar rezultate) |
| **Performance** | Lent (upload time) | Rapid (acces local) |
| **Audit** | Dificil de urmărit | Simplu (path-uri originale) |

---

## Resurse

### Documentație
- `services/node/api/app/main.py` - Implementare endpoints
- `services/node/ui/src/app/inference/page.tsx` - UI implementation
- `scripts/test_inference_onpremise.sh` - Test script

### Comenzi
```bash
make test-inference    # Test automat
make logs-node1        # Vezi logs
make status            # Verifică servicii
```

### API Docs
- Swagger UI: http://localhost:8001/docs
- Browse endpoint: `/api/infer/browse`
- Inference endpoint: `/api/infer`
- Results endpoint: `/api/infer/results/{job_id}`

---

**Autor**: Fed-Med-FL Team  
**Versiune**: 0.1.0  
**Status**: ✅ Production Ready pentru On-Premise Medical Imaging
