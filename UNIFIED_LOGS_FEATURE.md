# Unified Logs Viewer - Feature Implementation

## Overview
Unified the two separate tabs (Static Logs and Live Stream) into a single, intelligent logs viewer that automatically handles both historical and live logs.

## Problem
Previously, the observability feature had two separate tabs:
- **Static Logs**: Showed a snapshot of logs at a point in time
- **Live Stream**: Showed real-time logs for running jobs

This created a fragmented experience where users had to switch between tabs and couldn't see the complete log history when viewing live logs.

## Solution
Created a unified logs viewer that:
1. **Loads historical logs first**: When opening the logs dialog, it immediately loads all existing logs from the job
2. **Automatically starts live streaming**: If the job is running, it seamlessly continues with live log streaming
3. **Preserves complete history**: When a job completes, all logs (historical + live) are preserved in the same view
4. **Smart duplicate prevention**: Avoids showing duplicate log entries when transitioning from static to live

## Implementation Details

### New Component: `UnifiedLogsViewer.tsx`
Located at: `services/node/ui/src/components/UnifiedLogsViewer.tsx`

**Key Features:**
- Loads static logs on mount using `/api/jobs/{id}/logs/static`
- Automatically starts SSE streaming if job status is "running"
- Merges static and live logs without duplicates
- Updates job status in real-time
- Provides controls: Pause, Refresh, Clear, Export, Auto-scroll

**Workflow:**
```
1. Component mounts
   ↓
2. Load static logs (all historical logs)
   ↓
3. If job.status === 'running'
   ↓
4. Start SSE streaming (append new logs)
   ↓
5. When job completes, streaming stops automatically
   ↓
6. All logs remain visible (historical + live)
```

### Modified Files

#### `services/node/ui/src/app/jobs/page.tsx`
- Removed `Tabs` and `Tab` components
- Removed separate static/live log handling
- Simplified to use single `UnifiedLogsViewer` component
- Removed unused state: `logs`, `logsLoading`, `logsTab`

**Before:**
```tsx
<Tabs value={logsTab} onChange={(e, v) => setLogsTab(v)}>
  <Tab label="Static Logs" />
  <Tab label="Live Stream" />
</Tabs>
{logsTab === 0 && <StaticLogsView />}
{logsTab === 1 && <LiveLogsViewer />}
```

**After:**
```tsx
<UnifiedLogsViewer
  jobId={selectedJob.job_id}
  jobStatus={selectedJob.status}
  apiBase={API_BASE}
/>
```

## User Experience

### For Completed Jobs
1. User clicks "View Logs" on a completed job
2. All logs are loaded immediately
3. No streaming occurs (job is done)
4. User sees complete log history

### For Running Jobs
1. User clicks "View Logs" on a running job
2. Historical logs load first (what happened so far)
3. Live streaming starts automatically
4. New logs appear in real-time
5. When job completes, streaming stops
6. All logs remain visible

### For Pending Jobs
1. User clicks "View Logs" on a pending job
2. Shows "No logs available" (job hasn't started)
3. User can refresh to check for new logs

## UI Controls

| Control | Description |
|---------|-------------|
| 🔴 Live Logs / 📋 Job Logs | Indicator showing if streaming is active |
| Status Chip | Current job status (running, completed, failed, etc.) |
| Pause/Resume | Pause live streaming (useful for reading) |
| Refresh | Reload static logs and restart streaming if needed |
| Clear Display | Clear the log display (doesn't delete logs) |
| Export | Download all logs as a text file |
| Auto-scroll | Toggle automatic scrolling to newest logs |

## Benefits

1. **Seamless Experience**: No need to switch tabs
2. **Complete History**: See everything from start to finish
3. **Automatic Behavior**: Intelligently handles running vs completed jobs
4. **No Duplicates**: Smart merging prevents duplicate log entries
5. **Better UX**: Single, consistent interface for all log viewing

## Technical Details

### Duplicate Prevention
```typescript
setLogs((prev) => {
  const isDuplicate = prev.some(log => 
    log.message === data.message && log.timestamp === data.timestamp
  );
  
  if (isDuplicate) return prev;
  return [...prev, data];
});
```

### Automatic Streaming Detection
```typescript
useEffect(() => {
  const initialize = async () => {
    await loadStaticLogs();
    
    // If job is running, start live streaming
    if (jobStatus === 'running') {
      startStreaming();
    }
  };

  initialize();
}, [jobId]);
```

## Testing

### Test Case 1: View Completed Job Logs
1. Navigate to Jobs page
2. Click "View Logs" on a completed job
3. ✅ All logs should appear immediately
4. ✅ No streaming indicator should be shown
5. ✅ Status should show "completed"

### Test Case 2: View Running Job Logs
1. Start a new training or inference job
2. Immediately click "View Logs"
3. ✅ Historical logs should load first
4. ✅ "🔴 Live Logs" indicator should appear
5. ✅ New logs should stream in real-time
6. ✅ When job completes, streaming should stop
7. ✅ All logs should remain visible

### Test Case 3: Refresh Functionality
1. Open logs for any job
2. Click "Refresh" button
3. ✅ Logs should reload from server
4. ✅ If job is running, streaming should restart

### Test Case 4: Export Functionality
1. Open logs for any job with logs
2. Click "Export" button
3. ✅ File should download with format: `job-{id}-logs.txt`
4. ✅ File should contain all visible logs

## Files Changed

- ✅ `services/node/ui/src/app/jobs/page.tsx` - Simplified to use unified viewer
- ✅ `services/node/ui/src/components/UnifiedLogsViewer.tsx` - New unified component
- 📝 `services/node/ui/src/components/LiveLogsViewer.tsx` - Still exists but not used (can be removed)

## Future Enhancements

1. **Log Filtering**: Add ability to filter logs by severity (ERROR, INFO, etc.)
2. **Search**: Add search functionality to find specific log entries
3. **Timestamps Toggle**: Option to show/hide timestamps
4. **Color Themes**: Different color schemes for log viewer
5. **Log Levels**: Parse and highlight different log levels
6. **Performance**: Virtual scrolling for very large log files

## Deployment

```bash
# Rebuild UI services
docker compose build node1-ui node2-ui node3-ui

# Restart UI services
docker compose up -d node1-ui node2-ui node3-ui
```

## Status
✅ **IMPLEMENTED AND DEPLOYED**

The unified logs viewer is now live and working correctly. Users can view logs for any job with a seamless experience that automatically handles both historical and live logs.
