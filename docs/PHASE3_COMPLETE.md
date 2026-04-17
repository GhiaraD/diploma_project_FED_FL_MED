# Faza 3 - Node API + Worker Integration ✅

## Obiectiv
Implementarea API-ului pentru noduri și integrarea cu worker-ul Celery pentru joburi asincrone.

## Ce s-a implementat

### 1. Node API (`services/node/api/app/`) - ~800 linii

**FastAPI application** cu endpoints complete pentru:

#### Health & Status
- ✅ `GET /api/health` - Health check
- ✅ `GET /api/node/status` - Node statistics

#### Dataset Management
- ✅ `POST /api/data/upload` - Upload dataset (ZIP cu NORMAL/PNEUMONIA)
- ✅ `GET /api/data/list` - List datasets

#### Model Registry
- ✅ `GET /api/models/registry` - List models (candidate/deployed/archived)
- ✅ `POST /api/models/promote` - Promote candidate → deployed
- ✅ `GET /api/models/{model_id}` - Get model info

#### Training
- ✅ `POST /api/train/local` - Start local training
- ✅ `GET /api/train/status/{job_id}` - Get training status

#### Inference
- ✅ `POST /api/infer` - Run inference with Grad-CAM
- ✅ `GET /api/infer/results/{job_id}` - Get inference results

#### Federated Learning
- ✅ `POST /api/federated/join/{round_id}` - Join FL round
- ✅ `POST /api/federated/train/{round_id}` - Start FL training
- ✅ `GET /api/federated/status/{round_id}` - Get FL status

---

### 2. Worker Tasks (`services/node/api/app/tasks.py`) - ~400 linii

**Celery tasks** pentru joburi asincrone:

#### Training Tasks
- ✅ `train_local_model_task()` - Complete local training workflow
  - Load dataset
  - Initialize model
  - Train with early stopping
  - Save as candidate model
  - Update database

#### Inference Tasks
- ✅ `run_inference_task()` - Inference with Grad-CAM
  - Load deployed model
  - Run predictions
  - Generate Grad-CAM overlays
  - Save results to database

#### Federated Learning Tasks
- ✅ `federated_training_task()` - Complete FL workflow
  - Pull global model from central
  - Train locally
  - Compute delta
  - Push update to central
  - Save candidate model

---

### 3. Database Models (`services/node/api/app/database.py`) - ~150 linii

**SQLAlchemy models** pentru metadata:

#### Tables
- ✅ `Model` - Model registry (candidate/deployed/archived)
- ✅ `Job` - Job tracking (pending/running/completed/failed)
- ✅ `Dataset` - Dataset metadata
- ✅ `InferenceResult` - Inference results with Grad-CAM paths

---

### 4. Configuration (`services/node/api/app/config.py`) - ~100 linii

**Settings class** cu:
- ✅ Environment variables
- ✅ Storage paths (datasets, models, results, deltas)
- ✅ Model registry directories (candidate/deployed/archived)
- ✅ Database URL (SQLite)
- ✅ Redis/Celery configuration
- ✅ Central server URL
- ✅ ML defaults (model, batch size, epochs, lr)
- ✅ Auto-create directories

---

### 5. Schemas (`services/node/api/app/schemas.py`) - ~150 linii

**Pydantic models** pentru validation:
- ✅ Request/Response schemas pentru toate endpoints
- ✅ Type validation
- ✅ Documentation auto-generation

---

### 6. Docker Integration

#### API Dockerfile
```dockerfile
FROM python:3.11-slim
# Install system deps (OpenCV, PyTorch)
# Install node_core shared library
# Install FastAPI + dependencies
# Copy API code
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Worker Dockerfile
```dockerfile
FROM python:3.11-slim
# Install system deps
# Install node_core shared library
# Install Celery + dependencies
# Copy worker + API code (for tasks)
CMD ["celery", "-A", "run_worker:celery_app", "worker", "--loglevel=INFO"]
```

---

## Arhitectură

```
┌─────────────────────────────────────────────────────────────┐
│                         Node Portal (UI)                     │
│                      (Next.js + MUI)                         │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP REST
┌────────────────────────▼────────────────────────────────────┐
│                      Node API (FastAPI)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Endpoints:                                           │   │
│  │  - /api/health                                       │   │
│  │  - /api/data/upload                                  │   │
│  │  - /api/train/local                                  │   │
│  │  - /api/infer                                        │   │
│  │  - /api/federated/train/{round_id}                  │   │
│  │  - /api/models/registry                             │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ Celery Tasks
┌────────────────────────▼────────────────────────────────────┐
│                    Worker (Celery)                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Tasks:                                               │   │
│  │  - train_local_model_task()                         │   │
│  │  - run_inference_task()                             │   │
│  │  - federated_training_task()                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│                    node_core library                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ - ML models, training, inference                     │   │
│  │ - Grad-CAM                                           │   │
│  │ - FL client (delta, push/pull)                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                         │ HTTP REST
┌────────────────────────▼────────────────────────────────────┐
│                   Central Server                             │
│  - /model/global/{round_id}                                 │
│  - /update/submit                                            │
│  - /round/{id}/aggregate                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow Examples

### 1. Local Training

```python
# 1. Upload dataset
POST /api/data/upload
{
  "file": dataset.zip,
  "split": "train"
}
→ {"dataset_id": "dataset_train_abc123"}

# 2. Start training
POST /api/train/local
{
  "dataset_id": "dataset_train_abc123",
  "model_name": "resnet18",
  "num_epochs": 10
}
→ {"job_id": "train_xyz789", "status": "pending"}

# 3. Check status
GET /api/train/status/train_xyz789
→ {"status": "running", "result": null}

# 4. Wait for completion
GET /api/train/status/train_xyz789
→ {
  "status": "completed",
  "result": {
    "model_id": "resnet18_local_def456",
    "metrics": {"accuracy": 0.92}
  }
}

# 5. Promote to deployed
POST /api/models/promote
{
  "model_id": "resnet18_local_def456"
}
→ {"status": "success"}
```

### 2. Inference with Grad-CAM

```python
# 1. Run inference
POST /api/infer
{
  "image_paths": ["/storage/test/img1.jpg", "/storage/test/img2.jpg"],
  "generate_gradcam": true
}
→ {"job_id": "infer_abc123", "status": "pending"}

# 2. Get results
GET /api/infer/results/infer_abc123
→ {
  "status": "completed",
  "results": [
    {
      "predicted_class": 1,
      "confidence": 0.95,
      "gradcam_path": "/storage/results/inference/infer_abc123_0_gradcam.png"
    }
  ]
}
```

### 3. Federated Learning Round

```python
# 1. Join round
POST /api/federated/join/R-1
→ {"status": "success", "round_id": "R-1"}

# 2. Start FL training
POST /api/federated/train/R-1?dataset_id=dataset_train_abc123
→ {"job_id": "fl_train_R-1_xyz789", "status": "pending"}

# 3. Check status
GET /api/federated/status/R-1
→ {
  "round_id": "R-1",
  "local_status": "running",
  "central_status": {
    "participants": ["node1", "node2", "node3"],
    "updates_received": 1
  }
}

# 4. Wait for completion
GET /api/train/status/fl_train_R-1_xyz789
→ {
  "status": "completed",
  "result": {
    "model_id": "resnet18_R-1_candidate",
    "metrics": {"accuracy": 0.90, "f1": 0.88},
    "push_result": {"status": "accepted"}
  }
}
```

---

## Storage Structure

```
/storage/
├── datasets/
│   └── dataset_train_abc123/
│       ├── NORMAL/
│       └── PNEUMONIA/
├── models/
│   ├── candidate/
│   │   └── resnet18_R-1_candidate.pt
│   ├── deployed/
│   │   └── resnet18_deployed.pt
│   └── archived/
│       └── resnet18_old.pt
├── results/
│   ├── inference/
│   │   └── infer_abc123_0_gradcam.png
│   └── training/
│       └── train_xyz789_logs.json
├── deltas/
│   └── delta_node1_R-1.pt
└── node.db  # SQLite database
```

---

## Database Schema

```sql
-- Models registry
CREATE TABLE models (
    id INTEGER PRIMARY KEY,
    model_id TEXT UNIQUE,
    model_name TEXT,
    version TEXT,
    type TEXT,  -- candidate/deployed/archived
    round_id TEXT,
    base_model_hash TEXT,
    file_path TEXT,
    metrics JSON,
    created_at DATETIME,
    promoted_at DATETIME,
    archived_at DATETIME
);

-- Jobs tracking
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    job_id TEXT UNIQUE,
    job_type TEXT,  -- train/infer/federated_train
    status TEXT,  -- pending/running/completed/failed
    params JSON,
    result JSON,
    error TEXT,
    created_at DATETIME,
    started_at DATETIME,
    completed_at DATETIME
);

-- Datasets
CREATE TABLE datasets (
    id INTEGER PRIMARY KEY,
    dataset_id TEXT UNIQUE,
    name TEXT,
    path TEXT,
    split TEXT,
    num_samples INTEGER,
    num_normal INTEGER,
    num_pneumonia INTEGER,
    created_at DATETIME
);

-- Inference results
CREATE TABLE inference_results (
    id INTEGER PRIMARY KEY,
    result_id TEXT UNIQUE,
    job_id TEXT,
    model_id TEXT,
    image_path TEXT,
    predicted_class INTEGER,
    confidence FLOAT,
    probabilities JSON,
    gradcam_path TEXT,
    created_at DATETIME
);
```

---

## Environment Variables

```bash
# Node identification
NODE_ID=node1

# Storage
STORAGE_ROOT=/storage

# Database
DATABASE_URL=sqlite:///storage/node.db

# Redis/Celery
REDIS_URL=redis://node1-redis:6379/0

# Central server
CENTRAL_URL=http://central:8080

# ML settings
DEFAULT_MODEL=resnet18
DEFAULT_BATCH_SIZE=32
DEFAULT_NUM_EPOCHS=10
DEFAULT_LEARNING_RATE=0.001

# Device
DEVICE=cuda  # or cpu
```

---

## Testing

### 1. Start services

```bash
docker compose up node1-api node1-worker node1-redis
```

### 2. Test health

```bash
curl http://localhost:8001/api/health
```

### 3. Test training

```bash
# Upload dataset
curl -X POST http://localhost:8001/api/data/upload \
  -F "file=@dataset.zip" \
  -F "split=train"

# Start training
curl -X POST http://localhost:8001/api/train/local \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "dataset_train_abc123",
    "model_name": "resnet18",
    "num_epochs": 5
  }'
```

---

## Metrici Faza 3

- **Linii cod nou**: ~1,600 linii
- **Endpoints**: 15+ REST endpoints
- **Tasks**: 3 Celery tasks
- **Database tables**: 4 tables
- **Schemas**: 15+ Pydantic models

**Total proiect până acum**: ~4,600 linii cod + tests + docs

---

## Pași Următori (Faza 4)

Acum putem implementa **Central Server**:

1. **Central API** (`services/central/app/main.py`)
   - Round management
   - Model distribution
   - Update collection
   - Aggregation trigger

2. **Integration cu FedAvgAggregator**
   - Use `node_core.FedAvgAggregator`
   - Manage rounds
   - Aggregate updates

3. **Global model registry**
   - Version tracking
   - Round history

---

**Status**: ✅ COMPLET  
**Data finalizare**: 2026-04-16  
**Următoarea fază**: Faza 4 - Central Orchestrator
