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
  Grid,
  Divider,
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

interface TrainingRound {
  round_id: string;
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
  const [rounds, setRounds] = useState<TrainingRound[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [selectedRound, setSelectedRound] = useState<TrainingRound | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  useEffect(() => {
    fetchTrainingHistory();
    const interval = setInterval(fetchTrainingHistory, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const fetchTrainingHistory = async () => {
    try {
      setLoading(true);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/federated/history`);
      if (!response.ok) throw new Error('Failed to fetch training history');
      const data = await response.json();
      setRounds(data.rounds || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleViewDetails = (round: TrainingRound) => {
    setSelectedRound(round);
    setDetailsOpen(true);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon color="success" />;
      case 'failed':
        return <CancelIcon color="error" />;
      case 'running':
        return <RunningIcon color="primary" />;
      case 'pending':
        return <PendingIcon color="warning" />;
      default:
        return <PendingIcon color="disabled" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'running':
        return 'primary';
      case 'pending':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getParticipationStatus = (round: TrainingRound) => {
    const hasJoined = round.local_status !== 'not_started' && round.job_id !== null;
    return hasJoined;
  };

  const formatDuration = (start: string | null, end: string | null) => {
    if (!start || !end) return '-';
    const duration = new Date(end).getTime() - new Date(start).getTime();
    const minutes = Math.floor(duration / 60000);
    const seconds = Math.floor((duration % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('ro-RO', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Paginated data
  const paginatedRounds = rounds.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  return (
    <Layout title="Federated Learning">
      <Container maxWidth="xl">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4">
            Federated Learning History
          </Typography>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchTrainingHistory}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {loading && rounds.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Round ID</TableCell>
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
                  {paginatedRounds.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} align="center">
                        <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                          No federated learning rounds yet. Training rounds will appear here automatically.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : (
                    paginatedRounds.map((round) => {
                      const participated = getParticipationStatus(round);
                      
                      return (
                        <TableRow
                          key={round.round_id}
                          sx={{
                            backgroundColor: round.is_active ? 'action.hover' : 'inherit',
                            '&:hover': { backgroundColor: 'action.selected' },
                          }}
                        >
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography
                                variant="body2"
                                sx={{
                                  fontFamily: 'monospace',
                                  fontWeight: round.is_active ? 'bold' : 'normal',
                                }}
                              >
                                {round.round_id}
                              </Typography>
                              {round.is_active && (
                                <Chip label="ACTIVE" color="primary" size="small" />
                              )}
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              {getStatusIcon(round.local_status)}
                              <Chip
                                label={round.local_status || 'not started'}
                                size="small"
                                color={getStatusColor(round.local_status) as any}
                              />
                            </Box>
                          </TableCell>
                          <TableCell>
                            {participated ? (
                              <Chip
                                icon={<CheckCircleIcon />}
                                label="Yes"
                                size="small"
                                color="success"
                              />
                            ) : (
                              <Chip label="No" size="small" color="default" />
                            )}
                          </TableCell>
                          <TableCell>
                            {participated && round.dataset_name ? (
                              <Box>
                                <Typography variant="body2" fontWeight="medium">
                                  {round.dataset_name}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>
                                  {round.dataset_id}
                                </Typography>
                              </Box>
                            ) : participated && round.dataset_id ? (
                              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                {round.dataset_id}
                              </Typography>
                            ) : (
                              <Typography variant="body2" color="text.secondary">
                                -
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {formatDateTime(round.created_at)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {formatDuration(round.created_at, round.completed_at)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {round.model_id ? (
                              <Box>
                                <Typography variant="body2" sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                                  {round.model_id.substring(0, 20)}...
                                </Typography>
                                <Chip
                                  label={round.model_type}
                                  size="small"
                                  variant="outlined"
                                  sx={{ mt: 0.5 }}
                                />
                              </Box>
                            ) : (
                              <Typography variant="body2" color="text.secondary">
                                -
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            {round.metrics?.accuracy ? (
                              <Typography variant="body2" fontWeight="bold">
                                {(round.metrics.accuracy * 100).toFixed(2)}%
                              </Typography>
                            ) : (
                              <Typography variant="body2" color="text.secondary">
                                -
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell align="center">
                            <Tooltip title="View Details">
                              <IconButton
                                size="small"
                                color="primary"
                                onClick={() => handleViewDetails(round)}
                              >
                                <VisibilityIcon />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
              <TablePagination
                rowsPerPageOptions={[5, 10, 25, 50]}
                component="div"
                count={rounds.length}
                rowsPerPage={rowsPerPage}
                page={page}
                onPageChange={handleChangePage}
                onRowsPerPageChange={handleChangeRowsPerPage}
              />
            </TableContainer>

            {/* Details Dialog */}
            <Dialog
              open={detailsOpen}
              onClose={() => setDetailsOpen(false)}
              maxWidth="md"
              fullWidth
            >
              <DialogTitle>
                Training Round Details: {selectedRound?.round_id}
              </DialogTitle>
              <DialogContent>
                {selectedRound && (
                  <Box sx={{ pt: 2 }}>
                    <Grid container spacing={3}>
                      {/* General Info */}
                      <Grid item xs={12}>
                        <Typography variant="h6" gutterBottom>
                          General Information
                        </Typography>
                        <Divider sx={{ mb: 2 }} />
                      </Grid>
                      
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Round ID
                        </Typography>
                        <Typography variant="body1" fontWeight="bold">
                          {selectedRound.round_id}
                        </Typography>
                      </Grid>

                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Status
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                          {getStatusIcon(selectedRound.local_status)}
                          <Chip
                            label={selectedRound.local_status}
                            size="small"
                            color={getStatusColor(selectedRound.local_status) as any}
                          />
                        </Box>
                      </Grid>

                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Participated
                        </Typography>
                        <Typography variant="body1">
                          {getParticipationStatus(selectedRound) ? 'Yes' : 'No'}
                        </Typography>
                      </Grid>

                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Job ID
                        </Typography>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                          {selectedRound.job_id || '-'}
                        </Typography>
                      </Grid>

                      {/* Dataset Info */}
                      {selectedRound.dataset_id && (
                        <>
                          <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                              Dataset Information
                            </Typography>
                            <Divider sx={{ mb: 2 }} />
                          </Grid>

                          <Grid item xs={6}>
                            <Typography variant="body2" color="text.secondary">
                              Dataset Name
                            </Typography>
                            <Typography variant="body1" fontWeight="bold">
                              {selectedRound.dataset_name || '-'}
                            </Typography>
                          </Grid>

                          <Grid item xs={6}>
                            <Typography variant="body2" color="text.secondary">
                              Dataset ID
                            </Typography>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                              {selectedRound.dataset_id}
                            </Typography>
                          </Grid>
                        </>
                      )}

                      {/* Timing */}
                      <Grid item xs={12}>
                        <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                          Timing
                        </Typography>
                        <Divider sx={{ mb: 2 }} />
                      </Grid>

                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Started At
                        </Typography>
                        <Typography variant="body1">
                          {formatDateTime(selectedRound.created_at)}
                        </Typography>
                      </Grid>

                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Completed At
                        </Typography>
                        <Typography variant="body1">
                          {formatDateTime(selectedRound.completed_at)}
                        </Typography>
                      </Grid>

                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Duration
                        </Typography>
                        <Typography variant="body1">
                          {formatDuration(selectedRound.created_at, selectedRound.completed_at)}
                        </Typography>
                      </Grid>

                      {/* Model Info */}
                      {selectedRound.model_id && (
                        <>
                          <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                              Model Information
                            </Typography>
                            <Divider sx={{ mb: 2 }} />
                          </Grid>

                          <Grid item xs={12}>
                            <Typography variant="body2" color="text.secondary">
                              Model ID
                            </Typography>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                              {selectedRound.model_id}
                            </Typography>
                          </Grid>

                          <Grid item xs={6}>
                            <Typography variant="body2" color="text.secondary">
                              Model Type
                            </Typography>
                            <Chip
                              label={selectedRound.model_type}
                              size="small"
                              color="primary"
                              sx={{ mt: 0.5 }}
                            />
                          </Grid>
                        </>
                      )}

                      {/* Metrics */}
                      {selectedRound.metrics && (
                        <>
                          <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                              Performance Metrics
                            </Typography>
                            <Divider sx={{ mb: 2 }} />
                          </Grid>

                          <Grid item xs={6}>
                            <Typography variant="body2" color="text.secondary">
                              Accuracy
                            </Typography>
                            <Typography variant="h6" color="success.main">
                              {(selectedRound.metrics.accuracy * 100).toFixed(2)}%
                            </Typography>
                          </Grid>

                          {selectedRound.metrics.loss && (
                            <Grid item xs={6}>
                              <Typography variant="body2" color="text.secondary">
                                Loss
                              </Typography>
                              <Typography variant="h6">
                                {selectedRound.metrics.loss.toFixed(4)}
                              </Typography>
                            </Grid>
                          )}

                          {selectedRound.metrics.f1 && (
                            <Grid item xs={6}>
                              <Typography variant="body2" color="text.secondary">
                                F1 Score
                              </Typography>
                              <Typography variant="body1">
                                {(selectedRound.metrics.f1 * 100).toFixed(2)}%
                              </Typography>
                            </Grid>
                          )}

                          {selectedRound.metrics.precision && (
                            <Grid item xs={6}>
                              <Typography variant="body2" color="text.secondary">
                                Precision
                              </Typography>
                              <Typography variant="body1">
                                {(selectedRound.metrics.precision * 100).toFixed(2)}%
                              </Typography>
                            </Grid>
                          )}

                          {selectedRound.metrics.recall && (
                            <Grid item xs={6}>
                              <Typography variant="body2" color="text.secondary">
                                Recall
                              </Typography>
                              <Typography variant="body1">
                                {(selectedRound.metrics.recall * 100).toFixed(2)}%
                              </Typography>
                            </Grid>
                          )}

                          {selectedRound.metrics.auc && (
                            <Grid item xs={6}>
                              <Typography variant="body2" color="text.secondary">
                                AUC
                              </Typography>
                              <Typography variant="body1">
                                {(selectedRound.metrics.auc * 100).toFixed(2)}%
                              </Typography>
                            </Grid>
                          )}
                        </>
                      )}

                      {/* Central Status */}
                      {selectedRound.central_status && (
                        <>
                          <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                              Central Server Info
                            </Typography>
                            <Divider sx={{ mb: 2 }} />
                          </Grid>

                          <Grid item xs={12}>
                            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
                              <pre style={{ margin: 0, fontSize: '0.75rem', overflow: 'auto' }}>
                                {JSON.stringify(selectedRound.central_status, null, 2)}
                              </pre>
                            </Paper>
                          </Grid>
                        </>
                      )}
                    </Grid>
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
  );
}
