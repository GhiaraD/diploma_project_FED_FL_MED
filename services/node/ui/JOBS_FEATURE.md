# Jobs & Management Feature - Frontend

## Overview

Noua pagină **Jobs & Management** permite monitorizarea în timp real a tuturor job-urilor (training, inference, federated learning) cu vizualizare de log-uri live.

## Features Implemented ✅

### 1. Jobs List Page (`/jobs`)

**Location:** `src/app/jobs/page.tsx`

**Features:**
- ✅ Tabel cu toate job-urile (active și complete)
- ✅ Filtrare după status (pending, running, completed, failed)
- ✅ Filtrare după tip (train, infer, federated_train)
- ✅ Auto-refresh la fiecare 5 secunde (toggle on/off)
- ✅ Manual refresh button
- ✅ Status badges colorate
- ✅ Formatare date relative (2m ago, 1h ago)
- ✅ Afișare durată job
- ✅ Click pe job pentru a vedea logs

**Columns:**
- Job ID (truncated cu tooltip pentru full ID)
- Type (chip badge)
- Status (colored chip cu emoji)
- Created (relative time)
- Duration (formatted)
- Actions (view logs button)

### 2. Live Logs Viewer Component

**Location:** `src/components/LiveLogsViewer.tsx`

**Features:**
- ✅ **Real-time streaming** folosind Server-Sent Events (SSE)
- ✅ Auto-scroll la ultimul log (toggle on/off)
- ✅ Pause/Resume streaming
- ✅ Clear logs
- ✅ Export logs ca .txt file
- ✅ Color coding pentru mesaje (errors în roșu, success în verde)
- ✅ Status updates în timp real
- ✅ Connection error handling
- ✅ Auto-close când job se termină

### 3. Logs Dialog

**Features:**
- ✅ Tabs pentru Static vs Live logs
- ✅ Static logs: snapshot de logs (pentru job-uri complete)
- ✅ Live logs: streaming în timp real (pentru job-uri running)
- ✅ Auto-select tab bazat pe status job
- ✅ Job details (type, status)
- ✅ Close button

### 4. Updated Layout

**Location:** `src/components/Layout.tsx`

**Changes:**
- ✅ Added "Jobs" menu item cu WorkIcon
- ✅ Link către `/jobs` page

## UI Components

### Jobs Table
```tsx
┌─────────────────────────────────────────────────────────────┐
│  Jobs & Management                    [Auto-refresh] [🔄]   │
├─────────────────────────────────────────────────────────────┤
│  [All Status ▼] [All Types ▼]                               │
│                                                               │
│  Job ID              Type      Status    Created    Actions  │
│  ─────────────────────────────────────────────────────────  │
│  fl_train_R-3...    Federated  🟢 Running  2m ago    [👁️]   │
│  train_local...     Train      ✅ Complete 5m ago    [👁️]   │
│  infer_xyz...       Infer      ❌ Failed   10m ago   [👁️]   │
└─────────────────────────────────────────────────────────────┘
```

### Live Logs Viewer
```tsx
┌─────────────────────────────────────────────────────────────┐
│  Live Logs  [running]  ⏳                                    │
│  [⏸️] [🗑️] [💾] [Auto-scroll]                                │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │ [17:10:45] [node1] Starting local training...        │  │
│  │ [17:10:46] [node1] Loading dataset...                │  │
│  │ [17:10:47] [node1] ✓ Dataset loaded: 1390 samples   │  │
│  │ [17:10:48] Training:  10%|█  | 4/44 [00:11<01:58]   │  │
│  │ [17:10:49] Training:  20%|██ | 8/44 [00:22<01:30]   │  │
│  │ ▼ Auto-scrolling...                                   │  │
│  └───────────────────────────────────────────────────────┘  │
│  Total logs: 45                          ✅ Job Completed   │
└─────────────────────────────────────────────────────────────┘
```

## Technical Implementation

### Server-Sent Events (SSE)

```typescript
const eventSource = new EventSource(`${apiBase}/api/jobs/${jobId}/logs`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'status':
      setJobStatus(data.status);
      break;
    case 'log':
      setLogs(prev => [...prev, data]);
      break;
    case 'done':
      eventSource.close();
      break;
  }
};
```

### Auto-Refresh Jobs

```typescript
useEffect(() => {
  fetchJobs();
  
  if (autoRefresh) {
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }
}, [statusFilter, typeFilter, autoRefresh]);
```

### Color Coding

- **Success** (✅): Green - completed jobs
- **Running** (🟢): Blue - active jobs
- **Failed** (❌): Red - failed jobs
- **Pending** (⏳): Orange - queued jobs

### Log Message Colors

- **Errors** (ERROR, ✗): Red (#f48771)
- **Success** (✓, SUCCESS): Green (#89d185)
- **Info** (ℹ️): Blue (#569cd6)
- **Default**: White (#d4d4d4)

## API Integration

### Endpoints Used

1. **GET /api/jobs/list**
   - Fetch all jobs with filtering
   - Auto-refresh every 5 seconds

2. **GET /api/jobs/{job_id}/logs/static**
   - Fetch static logs for completed jobs
   - Used in "Static Logs" tab

3. **GET /api/jobs/{job_id}/logs** (SSE)
   - Stream live logs for running jobs
   - Used in "Live Stream" tab

## Usage

### View All Jobs

1. Click "Jobs" in sidebar
2. See list of all jobs
3. Use filters to narrow down
4. Toggle auto-refresh on/off

### View Job Logs

1. Click 👁️ icon on any job
2. Dialog opens with logs
3. For running jobs: "Live Stream" tab is active
4. For completed jobs: "Static Logs" tab is active

### Live Streaming

1. Open logs for a running job
2. Switch to "Live Stream" tab
3. Logs appear in real-time
4. Use controls:
   - ⏸️ Pause/Resume
   - 🗑️ Clear logs
   - 💾 Export logs
   - Auto-scroll toggle

### Export Logs

1. Open logs viewer
2. Click 💾 (Download) button
3. Logs saved as `job-{job_id}-logs.txt`

## File Structure

```
services/node/ui/src/
├── app/
│   └── jobs/
│       └── page.tsx          # Main jobs page
├── components/
│   ├── Layout.tsx            # Updated with Jobs menu
│   └── LiveLogsViewer.tsx    # Live logs streaming component
```

## Dependencies

All dependencies already exist in package.json:
- `@mui/material` - UI components
- `@mui/icons-material` - Icons
- `next` - React framework
- `react` - Core library

No additional packages needed! ✅

## Testing

### Test Jobs List
```bash
# Start services
docker-compose up -d

# Open browser
http://localhost:3001/jobs
```

### Test Live Streaming
```bash
# Start a training job
curl -X POST "http://localhost:8001/api/train/local" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "dataset_train_abc123",
    "model_name": "efficientnet_b0",
    "num_epochs": 2
  }'

# Open jobs page and click on the running job
# Switch to "Live Stream" tab
# Watch logs appear in real-time!
```

## Browser Compatibility

- ✅ Chrome/Edge (full support)
- ✅ Firefox (full support)
- ✅ Safari (full support)
- ⚠️ IE11 (not supported - EventSource not available)

## Performance

- **Auto-refresh**: 5 seconds interval (configurable)
- **SSE Connection**: Persistent, low overhead
- **Log Filtering**: Done server-side
- **Memory**: Logs cleared on dialog close
- **Network**: Minimal - only new logs transmitted

## Future Enhancements

- [ ] Search/filter logs in viewer
- [ ] Regex search in logs
- [ ] Log level filtering (INFO, WARNING, ERROR)
- [ ] Time range selection
- [ ] Multiple jobs comparison
- [ ] Metrics graphs (training progress)
- [ ] Notifications for job completion
- [ ] WebSocket alternative to SSE

## Troubleshooting

### Logs not streaming

**Check:**
1. Backend SSE endpoint working: `curl -N http://localhost:8001/api/jobs/{job_id}/logs`
2. CORS headers correct
3. Browser console for errors
4. Network tab for SSE connection

### Auto-refresh not working

**Check:**
1. Auto-refresh toggle is ON
2. No JavaScript errors in console
3. API endpoint responding

### Export not working

**Check:**
1. Browser allows downloads
2. Logs exist (not empty)
3. Console for errors

---

**Status**: ✅ Complete and Ready for Testing  
**Version**: 1.0.0  
**Date**: 2026-04-21
