# Observability & Management Feature

## Overview

Noua funcționalitate de observabilitate și management permite monitorizarea în timp real a job-urilor și vizualizarea log-urilor din timpul procesului de antrenare/inferență.

## Backend API Endpoints

### 1. List Jobs
```http
GET /api/jobs/list?status=running&job_type=federated_train&limit=50
```

**Query Parameters:**
- `status` (optional): Filter by status (pending, running, completed, failed)
- `job_type` (optional): Filter by type (train, infer, federated_train)
- `limit` (optional): Maximum number of jobs (default: 50)

**Response:**
```json
{
  "total": 10,
  "jobs": [
    {
      "job_id": "fl_train_R-TEST-3_aad96d48",
      "job_type": "federated_train",
      "status": "running",
      "params": {
        "round_id": "R-TEST-3",
        "dataset_id": "dataset_train_477f2544"
      },
      "result": null,
      "error": null,
      "created_at": "2026-04-21T17:10:43.000Z",
      "started_at": "2026-04-21T17:10:45.000Z",
      "completed_at": null,
      "duration": null
    }
  ]
}
```

### 2. Get Job Status
```http
GET /api/jobs/{job_id}/status
```

**Response:**
```json
{
  "job_id": "fl_train_R-TEST-3_aad96d48",
  "job_type": "federated_train",
  "status": "running",
  "params": {...},
  "result": null,
  "error": null,
  "created_at": "2026-04-21T17:10:43.000Z",
  "started_at": "2026-04-21T17:10:45.000Z",
  "completed_at": null,
  "duration": null,
  "celery_status": {
    "task_id": "1f62054f-04dc-46ef-974d-3e86db99dd9c",
    "state": "STARTED",
    "info": null
  }
}
```

### 3. Stream Job Logs (Real-time)
```http
GET /api/jobs/{job_id}/logs
```

**Response:** Server-Sent Events (SSE) stream

```
data: {"type":"status","status":"running","job_id":"fl_train_R-TEST-3_aad96d48"}

data: {"type":"log","timestamp":"2026-04-21T17:10:45.123Z","message":"[node1] Starting local training..."}

data: {"type":"log","timestamp":"2026-04-21T17:10:46.456Z","message":"Training:  10%|█         | 4/44 [00:11<01:58,  2.95s/it, loss=0.0699, acc=96.25%]"}

data: {"type":"status","status":"completed","result":{...}}

data: {"type":"done"}
```

**Event Types:**
- `status`: Job status update
- `log`: Log line from worker
- `error`: Error message
- `done`: Stream completed

### 4. Get Static Logs
```http
GET /api/jobs/{job_id}/logs/static?lines=100
```

**Query Parameters:**
- `lines` (optional): Number of log lines to return (default: 100)

**Response:**
```json
{
  "job_id": "fl_train_R-TEST-3_aad96d48",
  "status": "completed",
  "total_lines": 45,
  "logs": [
    {
      "timestamp": "2026-04-21T17:10:45.123Z",
      "message": "[node1] Starting local training..."
    },
    {
      "timestamp": "2026-04-21T17:10:46.456Z",
      "message": "Training:  10%|█         | 4/44 [00:11<01:58,  2.95s/it]"
    }
  ]
}
```

## Frontend UI Components

### 1. Jobs Management Page

**Location:** `/jobs` sau `/management`

**Features:**
- Tabel cu toate job-urile (active și complete)
- Filtrare după status și tip
- Sortare după dată
- Refresh automat pentru job-uri active
- Click pe job pentru detalii

**Columns:**
- Job ID
- Type (Train / Infer / Federated)
- Status (badge colorat)
- Created At
- Duration
- Actions (View Logs, View Details)

### 2. Job Details Modal/Page

**Features:**
- Status badge
- Job parameters
- Results (dacă completat)
- Error message (dacă failed)
- Timeline (created → started → completed)
- Button "View Logs"

### 3. Live Logs Viewer

**Features:**
- Real-time log streaming folosind EventSource
- Auto-scroll la ultimul log
- Filtrare logs (search)
- Color coding pentru diferite tipuri de mesaje
- Progress indicators pentru training
- Export logs (download ca .txt)

**Implementation Example:**
```javascript
const eventSource = new EventSource(`/api/jobs/${jobId}/logs`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'status':
      updateJobStatus(data.status);
      break;
    case 'log':
      appendLogLine(data.message);
      break;
    case 'done':
      eventSource.close();
      break;
  }
};
```

## UI Design Mockup

```
┌─────────────────────────────────────────────────────────────┐
│  Jobs & Management                                    🔄 Refresh │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Filters: [All Status ▼] [All Types ▼] [Search...]          │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Job ID              Type      Status    Created    ⚙️  │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ fl_train_R-3_aad   Federated  🟢 Running  2m ago   👁️  │  │
│  │ train_local_abc    Train      ✅ Complete 5m ago   👁️  │  │
│  │ infer_xyz_123      Infer      ❌ Failed   10m ago  👁️  │  │
│  │ fl_train_R-2_bcd   Federated  ✅ Complete 1h ago   👁️  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  [Load More]                                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Live Logs - fl_train_R-3_aad96d48              [Export] [X] │
├─────────────────────────────────────────────────────────────┤
│  Status: 🟢 Running                                          │
│  Type: Federated Training                                    │
│  Started: 2 minutes ago                                      │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ [17:10:45] [node1] Starting local training...        │  │
│  │ [17:10:46] [node1] Loading dataset...                │  │
│  │ [17:10:47] [node1] ✓ Dataset loaded: 1390 samples   │  │
│  │ [17:10:48] [node1] Connecting to Flower server...    │  │
│  │ [17:10:49] [node1] ✓ Connected                       │  │
│  │ [17:10:50] Training:  10%|█  | 4/44 [00:11<01:58]   │  │
│  │ [17:10:51] Training:  20%|██ | 8/44 [00:22<01:30]   │  │
│  │ [17:10:52] Training:  30%|███| 12/44 [00:33<01:15]  │  │
│  │ ▼ Auto-scrolling...                                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  [Pause Auto-scroll] [Clear] [Search in logs...]            │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### Phase 1: Backend (DONE ✅)
- [x] Add `/api/jobs/list` endpoint
- [x] Add `/api/jobs/{job_id}/status` endpoint
- [x] Add `/api/jobs/{job_id}/logs` SSE streaming endpoint
- [x] Add `/api/jobs/{job_id}/logs/static` endpoint

### Phase 2: Frontend UI
- [ ] Create Jobs Management page component
- [ ] Create Jobs table with filtering
- [ ] Create Job Details modal
- [ ] Create Live Logs viewer component
- [ ] Implement EventSource for real-time logs
- [ ] Add auto-refresh for active jobs
- [ ] Add export logs functionality

### Phase 3: Integration
- [ ] Add "Jobs" link to sidebar navigation
- [ ] Update existing pages to link to job details
- [ ] Add notifications for job completion
- [ ] Test with real training/inference jobs

## Technical Details

### Log Streaming Architecture

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│  Browser │◄────────│ FastAPI  │◄────────│  Docker  │
│          │  SSE    │  Server  │  logs   │ Container│
│          │         │          │         │ (Worker) │
└──────────┘         └──────────┘         └──────────┘
     │                     │                     │
     │  EventSource        │  subprocess         │
     │  /api/jobs/X/logs   │  docker logs -f     │
     │                     │                     │
     └─────────────────────┴─────────────────────┘
```

### Log Filtering

Logs sunt filtrate pentru a afișa doar liniile relevante pentru job-ul specific:
- Conține `job_id` în linie
- Conține `job_type` în linie
- Conține `[node_id]` în linie

### Performance Considerations

1. **Streaming**: Folosim SSE (Server-Sent Events) pentru streaming eficient
2. **Buffering**: Disable nginx buffering cu `X-Accel-Buffering: no`
3. **Filtering**: Filtrăm logs la nivel de server pentru a reduce traficul
4. **Pagination**: Limităm numărul de job-uri afișate (default 50)
5. **Auto-close**: Stream-ul se închide automat când job-ul se termină

## Testing

### Test SSE Streaming
```bash
# Test cu curl
curl -N http://localhost:8001/api/jobs/fl_train_R-3_aad96d48/logs

# Test cu JavaScript
const eventSource = new EventSource('http://localhost:8001/api/jobs/fl_train_R-3_aad96d48/logs');
eventSource.onmessage = (e) => console.log(JSON.parse(e.data));
```

### Test Static Logs
```bash
curl http://localhost:8001/api/jobs/fl_train_R-3_aad96d48/logs/static?lines=50
```

### Test Jobs List
```bash
curl http://localhost:8001/api/jobs/list?status=running
```

## Security Considerations

1. **Authentication**: Adaugă autentificare pentru endpoint-uri sensibile
2. **Rate Limiting**: Limitează numărul de conexiuni SSE per client
3. **Log Sanitization**: Filtrează informații sensibile din logs
4. **Access Control**: Verifică că userul are acces la job-ul respectiv

## Future Enhancements

1. **WebSocket Support**: Alternative la SSE pentru bi-directional communication
2. **Log Persistence**: Salvează logs în fișiere pentru istoric
3. **Advanced Filtering**: Regex search, log levels, time range
4. **Metrics Dashboard**: Grafice pentru training progress
5. **Alerts**: Notificări pentru job failures
6. **Export Formats**: JSON, CSV, PDF pentru logs

---

**Status**: Backend Complete ✅ | Frontend Pending 🔄  
**Version**: 1.0.0  
**Date**: 2026-04-21
