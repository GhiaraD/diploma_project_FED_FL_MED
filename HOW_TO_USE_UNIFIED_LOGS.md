# How to Use the Unified Logs Viewer

## Quick Start

1. **Access the UI**: Open your browser and navigate to:
   - Node 1: http://localhost:3001/jobs
   - Node 2: http://localhost:3002/jobs
   - Node 3: http://localhost:3003/jobs

2. **View Job Logs**: Click the 👁️ (eye) icon next to any job in the table

3. **That's it!** The logs viewer will automatically:
   - Load all historical logs
   - Start live streaming if the job is running
   - Show complete logs when the job finishes

## Features

### Automatic Behavior

**For Completed Jobs:**
- Opens with all logs already loaded
- No streaming (job is done)
- Ready to read immediately

**For Running Jobs:**
- Loads what happened so far
- Automatically starts live streaming
- Shows new logs in real-time
- Stops streaming when job completes
- Keeps all logs visible

**For Pending Jobs:**
- Shows "No logs available"
- Use Refresh button to check for updates

### Controls

| Button | What It Does |
|--------|--------------|
| **Pause/Resume** | Pause live streaming to read logs without them scrolling |
| **Refresh** | Reload logs from server (useful if connection was lost) |
| **Clear Display** | Clear the screen (doesn't delete actual logs) |
| **Export** | Download all logs as a text file |
| **Auto-scroll** | Toggle automatic scrolling to newest logs |

### Visual Indicators

- **🔴 Live Logs**: Streaming is active (job is running)
- **📋 Job Logs**: Viewing static logs (job is completed/pending)
- **Streaming Chip**: Shows when actively receiving new logs
- **Status Chip**: Current job status (running, completed, failed, etc.)

## Common Scenarios

### Scenario 1: Monitoring a Running Job
```
1. Start a training or inference job
2. Go to Jobs page
3. Click "View Logs" on the running job
4. Watch logs stream in real-time
5. When job completes, streaming stops automatically
6. All logs remain visible for review
```

### Scenario 2: Reviewing a Completed Job
```
1. Go to Jobs page
2. Click "View Logs" on any completed job
3. All logs load immediately
4. Scroll through to review what happened
5. Use Export to save logs if needed
```

### Scenario 3: Debugging a Failed Job
```
1. Filter jobs by status: "Failed"
2. Click "View Logs" on the failed job
3. Look for ERROR messages (shown in red)
4. Export logs for further analysis
```

### Scenario 4: Pausing to Read
```
1. Open logs for a running job
2. Logs are streaming fast
3. Click "Pause" button
4. Read the logs without them scrolling
5. Click "Resume" to continue streaming
```

## Tips

1. **Auto-scroll**: Keep it ON when monitoring live jobs, turn it OFF when you want to read specific sections

2. **Export**: Save logs before closing the dialog if you need them for later

3. **Refresh**: If logs seem stuck or connection was lost, click Refresh to reload

4. **Clear Display**: Use this to declutter the screen, but remember it doesn't delete the actual logs

5. **Filters**: Use the status and type filters on the main Jobs page to find specific jobs quickly

## Log Colors

The viewer automatically highlights certain log messages:

- **🟢 Green**: Success messages (✓, SUCCESS)
- **🔴 Red**: Error messages (ERROR, ✗)
- **🔵 Blue**: Status updates
- **⚪ White**: Normal log messages

## Keyboard Shortcuts

While the logs dialog is open:
- **Esc**: Close the dialog
- **Scroll**: Use mouse wheel or trackpad to scroll through logs
- **Ctrl+F**: Use browser's find feature to search in logs

## Troubleshooting

### Logs not loading?
- Check that the job exists
- Click Refresh button
- Check browser console for errors

### Streaming not working?
- Verify job status is "running"
- Check network connection
- Refresh the page

### Logs appear twice?
- This shouldn't happen (duplicate prevention is built-in)
- If it does, click Refresh to reload

### Can't see new logs?
- Check if Auto-scroll is ON
- Check if streaming is Paused
- Scroll to bottom manually

## API Endpoints Used

The unified logs viewer uses these endpoints:

1. **Static Logs**: `GET /api/jobs/{job_id}/logs/static?lines=500`
   - Loads historical logs
   - Used on initial load

2. **Live Stream**: `GET /api/jobs/{job_id}/logs` (SSE)
   - Server-Sent Events stream
   - Used for running jobs

## Example Workflow

```
User Action                    → System Response
─────────────────────────────────────────────────────────
Click "View Logs"              → Load static logs
                               → Show loading indicator
                               
Static logs loaded             → Display all historical logs
                               → Check job status
                               
If job is running              → Start SSE streaming
                               → Show "🔴 Live Logs"
                               → Show "Streaming" chip
                               
New log arrives                → Append to display
                               → Auto-scroll if enabled
                               
Job completes                  → Stop streaming
                               → Update status chip
                               → Keep all logs visible
```

## Access URLs

- **Node 1 Jobs**: http://localhost:3001/jobs
- **Node 2 Jobs**: http://localhost:3002/jobs
- **Node 3 Jobs**: http://localhost:3003/jobs

Each node has its own independent job queue and logs.

## Summary

The unified logs viewer provides a seamless experience for viewing both historical and live logs in a single interface. It automatically handles the complexity of loading static logs and transitioning to live streaming, giving you a complete view of your job's execution from start to finish.

No more switching between tabs - just open the logs and everything is there! 🎉
