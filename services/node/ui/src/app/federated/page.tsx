'use client';
import { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Button,
  Box,
  CircularProgress,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  TextField,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Visibility as VisibilityIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  HourglassEmpty as PendingIcon,
  PlayCircle as RunningIcon,
} from '@mui/icons-material';
import Layout from '@/components/Layout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { API_BASE } from '@/config/api';

interface TrainingSession {
  session_id: string;
  is_active: boolean;
  local_status: string;
  job_id: string | null;
  created_at: string | null;
  completed_at: string | null;
  model_id: string | null;
  model_type: string | null;
  dataset_id: string | null;
  dataset_name: string | null;
  metrics: any;
  central_status: any;
}

export default function FederatedPage() {
  const [sessions, setSessions] = useState<TrainingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [selectedSession, setSelectedSession] = useState<TrainingSession | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const { token } = useAuth();

  useEffect(() => {
    if (token) {
      fetchHistory();
      const interval = setInterval(fetchHistory, 10000);
      return () => clearInterval(interval);
    }
  }, [token]);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const apiBase = API_BASE;
      const response = await fetch(`${apiBase}/api/federated/history`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch training history');
      const data = await response.json();
      setSessions(data.rounds || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage);

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleViewDetails = (session: TrainingSession) => {
    setSelectedSession(session);
    setDetailsOpen(true);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircleIcon color="success" />;
      case 'failed':    return <CancelIcon color="error" />;
      case 'running':   return <RunningIcon color="primary" />;
      case 'pending':   return <PendingIcon color="warning" />;
      default:          return <PendingIcon color="disabled" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed':    return 'error';
      case 'running':   return 'primary';
      case 'pending':   return 'warning';
      default:          return 'default';
    }
  };

  const hasParticipated = (s: TrainingSession) =>
    s.local_status !== 'not_started' && s.job_id !== null;

  const formatDuration = (start: string | null, end: string | null) => {
    if (!start || !end) return '-';
    const ms = new Date(end).getTime() - new Date(start).getTime();
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('ro-RO', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const filteredSessions = sessions.filter((s) =>
    searchQuery === '' || s.session_id.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const paginatedSessions = filteredSessions.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  return (
    <ProtectedRoute>
      <Layout title="Federated Learning">
        <Container maxWidth="xl">
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h4">Federated Learning History</Typography>
            <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchHistory} disabled={loading}>
              Refresh
            </Button>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {loading && sessions.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              <Paper sx={{ p: 2, mb: 2 }}>
                <TextField
                  label="Search by Session ID"
                  value={searchQuery}
                  onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
                  size="small"
                  sx={{ minWidth: 320 }}
                  placeholder="e.g. federated_abc123..."
                />
              </Paper>

              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Session ID</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Participated</TableCell>
                      <TableCell>Dataset Used</TableCell>
                      <TableCell>Start Time</TableCell>
                      <TableCell>Duration</TableCell>
                      <TableCell>Model</TableCell>
                      <TableCell>Accuracy</TableCell>
                      <TableCell align="center">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {paginatedSessions.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={9} align="center">
                          <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                            {searchQuery
                              ? `No sessions found matching "${searchQuery}"`
                              : 'No federated learning sessions yet. Training sessions will appear here automatically.'}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedSessions.map((s: TrainingSession) => (
                        <TableRow
                          key={s.session_id}
                          sx={{
                            backgroundColor: s.is_active ? 'action.hover' : 'inherit',
                            '&:hover': { backgroundColor: 'action.selected' },
                          }}
                        >
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography
                                variant="body2"
                                sx={{ fontFamily: 'monospace', fontWeight: s.is_active ? 'bold' : 'normal' }}
                              >
                                {s.session_id}
                              </Typography>
                              {s.is_active && <Chip label="ACTIVE" color="primary" size="small" />}
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              {getStatusIcon(s.local_status)}
                              <Chip
                                label={s.local_status || 'not started'}
                                size="small"
                                color={getStatusColor(s.local_status) as any}
                              />
                            </Box>
                          </TableCell>
                          <TableCell>
                            {hasParticipated(s)
                              ? <Chip icon={<CheckCircleIcon />} label="Yes" size="small" color="success" />
                              : <Chip label="No" size="small" color="default" />}
                          </TableCell>
                          <TableCell>
                            {hasParticipated(s) && s.dataset_name ? (
                              <Box>
                                <Typography variant="body2" fontWeight="medium">{s.dataset_name}</Typography>
                                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>
                                  {s.dataset_id}
                                </Typography>
                              </Box>
                            ) : hasParticipated(s) && s.dataset_id ? (
                              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                {s.dataset_id}
                              </Typography>
                            ) : (
                              <Typography variant="body2" color="text.secondary">-</Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{formatDateTime(s.created_at)}</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{formatDuration(s.created_at, s.completed_at)}</Typography>
                          </TableCell>
                          <TableCell>
                            {s.model_id ? (
                              <Box>
                                <Typography variant="body2" sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                                  {s.model_id.substring(0, 20)}...
                                </Typography>
                                <Chip label={s.model_type === 'deployed' ? 'active' : s.model_type} size="small" variant="outlined" sx={{ mt: 0.5 }} />
                              </Box>
                            ) : (
                              <Typography variant="body2" color="text.secondary">-</Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            {s.metrics?.accuracy ? (
                              <Typography variant="body2" fontWeight="bold">
                                {(s.metrics.accuracy * 100).toFixed(2)}%
                              </Typography>
                            ) : (
                              <Typography variant="body2" color="text.secondary">-</Typography>
                            )}
                          </TableCell>
                          <TableCell align="center">
                            <Tooltip title="View Details">
                              <IconButton size="small" color="primary" onClick={() => handleViewDetails(s)}>
                                <VisibilityIcon />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
                <TablePagination
                  rowsPerPageOptions={[5, 10, 25, 50]}
                  component="div"
                  count={filteredSessions.length}
                  rowsPerPage={rowsPerPage}
                  page={page}
                  onPageChange={handleChangePage}
                  onRowsPerPageChange={handleChangeRowsPerPage}
                />
              </TableContainer>

              {/* Details Dialog */}
              <Dialog open={detailsOpen} onClose={() => setDetailsOpen(false)} maxWidth="md" fullWidth>
                <DialogTitle>
                  Training Session Details: {selectedSession?.session_id}
                </DialogTitle>
                <DialogContent>
                  {selectedSession && (
                    <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>

                      <Box>
                        <Typography variant="h6" gutterBottom>General Information</Typography>
                        <Divider sx={{ mb: 2 }} />
                        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                          <Box>
                            <Typography variant="body2" color="text.secondary">Session ID</Typography>
                            <Typography variant="body1" fontWeight="bold" sx={{ wordBreak: 'break-all' }}>
                              {selectedSession.session_id}
                            </Typography>
                          </Box>
                          <Box>
                            <Typography variant="body2" color="text.secondary">Status</Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                              {getStatusIcon(selectedSession.local_status)}
                              <Chip
                                label={selectedSession.local_status}
                                size="small"
                                color={getStatusColor(selectedSession.local_status) as any}
                              />
                            </Box>
                          </Box>
                          <Box>
                            <Typography variant="body2" color="text.secondary">Participated</Typography>
                            <Typography variant="body1">{hasParticipated(selectedSession) ? 'Yes' : 'No'}</Typography>
                          </Box>
                          <Box>
                            <Typography variant="body2" color="text.secondary">Job ID</Typography>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem', wordBreak: 'break-all' }}>
                              {selectedSession.job_id || '-'}
                            </Typography>
                          </Box>
                        </Box>
                      </Box>

                      {selectedSession.dataset_id && (
                        <Box>
                          <Typography variant="h6" gutterBottom>Dataset Information</Typography>
                          <Divider sx={{ mb: 2 }} />
                          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                            <Box>
                              <Typography variant="body2" color="text.secondary">Dataset Name</Typography>
                              <Typography variant="body1" fontWeight="bold" sx={{ wordBreak: 'break-all' }}>
                                {selectedSession.dataset_name || '-'}
                              </Typography>
                            </Box>
                            <Box>
                              <Typography variant="body2" color="text.secondary">Dataset ID</Typography>
                              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem', wordBreak: 'break-all' }}>
                                {selectedSession.dataset_id}
                              </Typography>
                            </Box>
                          </Box>
                        </Box>
                      )}

                      <Box>
                        <Typography variant="h6" gutterBottom>Timing</Typography>
                        <Divider sx={{ mb: 2 }} />
                        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                          <Box>
                            <Typography variant="body2" color="text.secondary">Started At</Typography>
                            <Typography variant="body1">{formatDateTime(selectedSession.created_at)}</Typography>
                          </Box>
                          <Box>
                            <Typography variant="body2" color="text.secondary">Completed At</Typography>
                            <Typography variant="body1">{formatDateTime(selectedSession.completed_at)}</Typography>
                          </Box>
                          <Box>
                            <Typography variant="body2" color="text.secondary">Duration</Typography>
                            <Typography variant="body1">{formatDuration(selectedSession.created_at, selectedSession.completed_at)}</Typography>
                          </Box>
                        </Box>
                      </Box>

                      {selectedSession.model_id && (
                        <Box>
                          <Typography variant="h6" gutterBottom>Model Information</Typography>
                          <Divider sx={{ mb: 2 }} />
                          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                            <Box sx={{ gridColumn: '1 / -1' }}>
                              <Typography variant="body2" color="text.secondary">Model ID</Typography>
                              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem', wordBreak: 'break-all' }}>
                                {selectedSession.model_id}
                              </Typography>
                            </Box>
                            <Box>
                              <Typography variant="body2" color="text.secondary">Model Type</Typography>
                              <Chip label={selectedSession.model_type === 'deployed' ? 'active' : selectedSession.model_type} size="small" color="primary" sx={{ mt: 0.5 }} />
                            </Box>
                          </Box>
                        </Box>
                      )}

                      {selectedSession.metrics && (
                        <Box>
                          <Typography variant="h6" gutterBottom>Performance Metrics</Typography>
                          <Divider sx={{ mb: 2 }} />
                          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                            <Box>
                              <Typography variant="body2" color="text.secondary">Accuracy</Typography>
                              <Typography variant="body1" fontWeight="bold" color="success.main">
                                {(selectedSession.metrics.accuracy * 100).toFixed(2)}%
                              </Typography>
                            </Box>
                            {selectedSession.metrics.loss && (
                              <Box>
                                <Typography variant="body2" color="text.secondary">Loss</Typography>
                                <Typography variant="body1" fontWeight="bold">{selectedSession.metrics.loss.toFixed(4)}</Typography>
                              </Box>
                            )}
                            {selectedSession.metrics.f1 && (
                              <Box>
                                <Typography variant="body2" color="text.secondary">F1 Score</Typography>
                                <Typography variant="body1">{(selectedSession.metrics.f1 * 100).toFixed(2)}%</Typography>
                              </Box>
                            )}
                            {selectedSession.metrics.precision && (
                              <Box>
                                <Typography variant="body2" color="text.secondary">Precision</Typography>
                                <Typography variant="body1">{(selectedSession.metrics.precision * 100).toFixed(2)}%</Typography>
                              </Box>
                            )}
                            {selectedSession.metrics.recall && (
                              <Box>
                                <Typography variant="body2" color="text.secondary">Recall</Typography>
                                <Typography variant="body1">{(selectedSession.metrics.recall * 100).toFixed(2)}%</Typography>
                              </Box>
                            )}
                            {selectedSession.metrics.auc && (
                              <Box>
                                <Typography variant="body2" color="text.secondary">AUC</Typography>
                                <Typography variant="body1">{(selectedSession.metrics.auc * 100).toFixed(2)}%</Typography>
                              </Box>
                            )}
                          </Box>
                        </Box>
                      )}

                      {selectedSession.central_status && (
                        <Box>
                          <Typography variant="h6" gutterBottom>Central Server Info</Typography>
                          <Divider sx={{ mb: 2 }} />
                          <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
                            <pre style={{ margin: 0, fontSize: '0.75rem', overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                              {JSON.stringify(selectedSession.central_status, null, 2)}
                            </pre>
                          </Paper>
                        </Box>
                      )}

                    </Box>
                  )}
                </DialogContent>
                <DialogActions>
                  <Button onClick={() => setDetailsOpen(false)}>Close</Button>
                </DialogActions>
              </Dialog>
            </>
          )}
        </Container>
      </Layout>
    </ProtectedRoute>
  );
}
