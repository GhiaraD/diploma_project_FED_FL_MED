'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Clear as ClearIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

interface LogEntry {
  timestamp?: string;
  message: string;
  type?: 'log' | 'status' | 'error' | 'done';
  status?: string;
  error?: string;
}

interface UnifiedLogsViewerProps {
  jobId: string;
  jobStatus: string;
  apiBase: string;
  token: string;
}

export default function UnifiedLogsViewer({ jobId, jobStatus, apiBase, token }: UnifiedLogsViewerProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [currentStatus, setCurrentStatus] = useState<string>(jobStatus);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingStatic, setIsLoadingStatic] = useState(true);
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Load static logs
  const loadStaticLogs = useCallback(async () => {
    if (isPaused) return; // Don't load if paused
    
    setIsLoadingStatic(true);
    setError(null);

    try {
      const response = await fetch(`${apiBase}/api/jobs/${jobId}/logs/static?lines=1000`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const data = await response.json();
      
      // Update logs completely (replace, don't append)
      setLogs(data.logs.map((log: any) => ({
        timestamp: log.timestamp,
        message: log.message,
        type: 'log'
      })));
      
      // Update status from job data
      if (data.status) {
        setCurrentStatus(data.status);
        
        // Stop polling if job is completed or failed
        if (data.status === 'completed' || data.status === 'failed') {
          stopPolling();
        }
      }
    } catch (err: any) {
      console.error('Error fetching static logs:', err);
      setError(err.message);
    } finally {
      setIsLoadingStatic(false);
    }
  }, [jobId, token, apiBase, isPaused]);

  // Start polling logs (for running jobs)
  const startPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    setIsPolling(true);
    
    // Poll every 1 second
    pollingIntervalRef.current = setInterval(() => {
      loadStaticLogs();
    }, 1000);
  };

  // Stop polling
  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  };

  // Toggle pause
  const togglePause = () => {
    const newPausedState = !isPaused;
    setIsPaused(newPausedState);
    
    // If unpausing and job is running, resume polling
    if (!newPausedState && currentStatus === 'running') {
      startPolling();
    } else if (newPausedState) {
      stopPolling();
    }
  };

  // Clear logs
  const clearLogs = () => {
    setLogs([]);
  };

  // Refresh logs (reload static logs)
  const refreshLogs = async () => {
    stopPolling();
    await loadStaticLogs();
    
    // If job is still running, restart polling
    if (currentStatus === 'running') {
      startPolling();
    }
  };

  // Export logs
  const exportLogs = () => {
    const logText = logs
      .filter((log) => log.type === 'log' || !log.type)
      .map((log) => log.timestamp ? `[${log.timestamp}] ${log.message}` : log.message)
      .join('\n');

    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `job-${jobId}-logs.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Initialize: Load static logs, then start polling if running
  useEffect(() => {
    const initialize = async () => {
      await loadStaticLogs();
      
      // If job is running, start polling
      if (jobStatus === 'running') {
        startPolling();
      }
    };

    initialize();

    return () => stopPolling();
  }, [jobId, loadStaticLogs]);

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'running': return 'primary';
      case 'failed': return 'error';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
            {isPolling ? '🔴 Live Logs' : '📋 Job Logs'}
          </Typography>
          <Chip
            label={currentStatus}
            color={getStatusColor(currentStatus)}
            size="small"
          />
          {isLoadingStatic && (
            <CircularProgress size={16} />
          )}
          {isPolling && (
            <Chip
              label="Auto-refresh"
              color="success"
              size="small"
              icon={<CircularProgress size={12} sx={{ color: 'white !important' }} />}
            />
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          {isPolling && (
            <Tooltip title={isPaused ? 'Resume' : 'Pause'}>
              <IconButton onClick={togglePause} size="small" color={isPaused ? 'warning' : 'default'}>
                {isPaused ? <PlayIcon /> : <PauseIcon />}
              </IconButton>
            </Tooltip>
          )}
          
          <Tooltip title="Refresh logs">
            <IconButton onClick={refreshLogs} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Clear display">
            <IconButton onClick={clearLogs} size="small">
              <ClearIcon />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Export logs">
            <IconButton onClick={exportLogs} size="small" disabled={logs.length === 0}>
              <DownloadIcon />
            </IconButton>
          </Tooltip>

          <Button
            variant={autoScroll ? 'contained' : 'outlined'}
            onClick={() => setAutoScroll(!autoScroll)}
            size="small"
          >
            Auto-scroll
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {isPaused && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Auto-refresh paused - logs will not update
        </Alert>
      )}

      {/* Logs Container */}
      <Paper
        sx={{
          p: 2,
          bgcolor: '#1e1e1e',
          color: '#d4d4d4',
          fontFamily: 'monospace',
          fontSize: '0.875rem',
          maxHeight: '500px',
          overflow: 'auto',
        }}
      >
        {isLoadingStatic && logs.length === 0 ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={20} />
            <Typography color="text.secondary">
              Loading logs...
            </Typography>
          </Box>
        ) : logs.length === 0 ? (
          <Typography color="text.secondary">
            No logs available for this job
          </Typography>
        ) : (
          logs.map((log, index) => {
            // Only render actual log messages, not status/error types
            if (log.type === 'log' || !log.type) {
              return (
                <Box key={index} sx={{ mb: 0.5 }}>
                  <Typography
                    component="pre"
                    sx={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontFamily: 'inherit',
                      fontSize: 'inherit',
                      color: log.message?.includes('ERROR') || log.message?.includes('✗') || log.message?.includes('❌')
                        ? '#f48771' 
                        : log.message?.includes('✓') || log.message?.includes('✅') || log.message?.includes('SUCCESS')
                        ? '#89d185'
                        : 'inherit',
                    }}
                  >
                    {log.message}
                  </Typography>
                </Box>
              );
            }
            return null;
          })
        )}
        <div ref={logsEndRef} />
      </Paper>

      {/* Stats */}
      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="caption" color="text.secondary">
          Total logs: {logs.filter(l => l.type === 'log' || !l.type).length}
          {isPolling && ' • Auto-refreshing every 1s'}
        </Typography>
        
        {currentStatus === 'completed' && (
          <Chip label="✅ Job Completed" color="success" size="small" />
        )}
        {currentStatus === 'failed' && (
          <Chip label="❌ Job Failed" color="error" size="small" />
        )}
      </Box>
    </Box>
  );
}
