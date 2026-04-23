'use client';
import { useState, useEffect, useRef } from 'react';
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
} from '@mui/icons-material';

interface LogEntry {
  type: 'log' | 'status' | 'error' | 'done';
  timestamp?: string;
  message?: string;
  status?: string;
  result?: any;
  error?: string;
}

interface LiveLogsViewerProps {
  jobId: string;
  apiBase: string;
  onClose?: () => void;
}

export default function LiveLogsViewer({ jobId, apiBase, onClose }: LiveLogsViewerProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [jobStatus, setJobStatus] = useState<string>('unknown');
  const [error, setError] = useState<string | null>(null);
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Start streaming logs
  const startStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setIsStreaming(true);
    setError(null);

    const eventSource = new EventSource(`${apiBase}/api/jobs/${jobId}/logs`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data: LogEntry = JSON.parse(event.data);
        
        if (!isPaused) {
          setLogs((prev) => [...prev, data]);
        }

        // Update job status
        if (data.type === 'status' && data.status) {
          setJobStatus(data.status);
        }

        // Close stream when done
        if (data.type === 'done') {
          eventSource.close();
          setIsStreaming(false);
        }
      } catch (err) {
        console.error('Error parsing log event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('EventSource error:', err);
      setError('Connection to log stream lost');
      setIsStreaming(false);
      eventSource.close();
    };
  };

  // Stop streaming
  const stopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
  };

  // Toggle pause
  const togglePause = () => {
    setIsPaused(!isPaused);
  };

  // Clear logs
  const clearLogs = () => {
    setLogs([]);
  };

  // Export logs
  const exportLogs = () => {
    const logText = logs
      .filter((log) => log.type === 'log')
      .map((log) => `[${log.timestamp}] ${log.message}`)
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

  // Start streaming on mount
  useEffect(() => {
    startStreaming();
    return () => stopStreaming();
  }, [jobId]);

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
          <Typography variant="h6">Live Logs</Typography>
          <Chip
            label={jobStatus}
            color={getStatusColor(jobStatus)}
            size="small"
          />
          {isStreaming && (
            <CircularProgress size={20} />
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title={isPaused ? 'Resume' : 'Pause'}>
            <IconButton onClick={togglePause} size="small" color={isPaused ? 'warning' : 'default'}>
              {isPaused ? <PlayIcon /> : <PauseIcon />}
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Clear logs">
            <IconButton onClick={clearLogs} size="small">
              <ClearIcon />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Export logs">
            <IconButton onClick={exportLogs} size="small">
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
          Streaming paused - new logs will not be displayed
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
          maxHeight: '600px',
          overflow: 'auto',
        }}
      >
        {logs.length === 0 ? (
          <Typography color="text.secondary">
            Waiting for logs...
          </Typography>
        ) : (
          logs.map((log, index) => {
            if (log.type === 'log') {
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
                      color: log.message?.includes('ERROR') || log.message?.includes('✗') 
                        ? '#f48771' 
                        : log.message?.includes('✓') || log.message?.includes('SUCCESS')
                        ? '#89d185'
                        : 'inherit',
                    }}
                  >
                    {log.message}
                  </Typography>
                </Box>
              );
            } else if (log.type === 'status') {
              return (
                <Box key={index} sx={{ mb: 1, p: 1, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                  <Typography sx={{ color: '#569cd6' }}>
                    ℹ️ Status: {log.status}
                  </Typography>
                </Box>
              );
            } else if (log.type === 'error') {
              return (
                <Box key={index} sx={{ mb: 1, p: 1, bgcolor: 'rgba(255,0,0,0.1)', borderRadius: 1 }}>
                  <Typography sx={{ color: '#f48771' }}>
                    ❌ Error: {log.error}
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
          Total logs: {logs.filter(l => l.type === 'log').length}
        </Typography>
        
        {jobStatus === 'completed' && (
          <Chip label="✅ Job Completed" color="success" size="small" />
        )}
        {jobStatus === 'failed' && (
          <Chip label="❌ Job Failed" color="error" size="small" />
        )}
      </Box>
    </Box>
  );
}
