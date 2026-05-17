"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Layout from '@/components/Layout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { API_BASE } from '@/config/api';
import {
  Container,
  Paper,
  Typography,
  Box,
  TextField,
  MenuItem,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  CircularProgress,
  Alert,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Security as SecurityIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Block as BlockIcon,
  ExitToApp as ExitToAppIcon,
  VpnKey as VpnKeyIcon,
  Person as PersonIcon,
  Warning as WarningIcon,
  Description as DescriptionIcon,
  Visibility as VisibilityIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';

interface AuditLog {
  id: string;
  timestamp: string;
  event_type: string;
  user_id: string | null;
  node_id: string;
  endpoint: string | null;
  ip_address: string | null;
  response_status: number | null;
  duration_ms: number | null;
  details: any;
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('all');
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  
  const { token } = useAuth();

  useEffect(() => {
    if (token) {
      fetchAuditLogs();
    }
  }, [token]);

  const fetchAuditLogs = async () => {
    try {
      setIsLoading(true);

      const response = await fetch(`${API_BASE}/api/auth/audit-logs?limit=100`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch audit logs');
      }

      const data = await response.json();
      setLogs(data);
      setError('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'login_success':
        return <CheckCircleIcon fontSize="small" />;
      case 'login_failed':
        return <CancelIcon fontSize="small" />;
      case 'login_blocked':
        return <BlockIcon fontSize="small" />;
      case 'logout':
        return <ExitToAppIcon fontSize="small" />;
      case 'password_changed':
        return <VpnKeyIcon fontSize="small" />;
      case 'user_created':
        return <PersonIcon fontSize="small" />;
      case 'user_deactivated':
        return <BlockIcon fontSize="small" />;
      case 'api_key_created':
        return <VpnKeyIcon fontSize="small" />;
      case 'api_key_revoked':
        return <CancelIcon fontSize="small" />;
      case 'permission_denied':
        return <WarningIcon fontSize="small" />;
      default:
        return <DescriptionIcon fontSize="small" />;
    }
  };

  const getEventColor = (eventType: string): "success" | "error" | "warning" | "info" | "default" => {
    if (eventType.includes('success')) return 'success';
    if (eventType.includes('failed') || eventType.includes('denied')) return 'error';
    if (eventType.includes('blocked')) return 'warning';
    return 'info';
  };

  const getStatusColor = (status: number | null) => {
    if (!status) return 'default';
    if (status < 300) return 'success';
    if (status < 400) return 'info';
    if (status < 500) return 'warning';
    return 'error';
  };

  const openDetailsDialog = (log: AuditLog) => {
    setSelectedLog(log);
    setDetailsDialogOpen(true);
  };

  const closeDetailsDialog = () => {
    setSelectedLog(null);
    setDetailsDialogOpen(false);
  };

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const filteredLogs = logs.filter(log => {
    const matchesSearch = filter === '' || 
      log.event_type.toLowerCase().includes(filter.toLowerCase()) ||
      log.endpoint?.toLowerCase().includes(filter.toLowerCase()) ||
      log.user_id?.toLowerCase().includes(filter.toLowerCase());
    
    const matchesEventType = eventTypeFilter === 'all' || log.event_type === eventTypeFilter;
    
    return matchesSearch && matchesEventType;
  });

  const eventTypes = ['all', ...Array.from(new Set(logs.map(log => log.event_type)))];

  const paginatedLogs = filteredLogs.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage,
  );

  return (
    <ProtectedRoute>
      <Layout title="Security Audit">
        <Container maxWidth="xl">
          {/* Header */}
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
            <SecurityIcon sx={{ fontSize: 40, mr: 2, color: 'primary.main' }} />
            <Box>
              <Typography variant="h4" component="h1" gutterBottom>
                Security Audit Logs
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Monitor all security events and user activities
              </Typography>
            </Box>
          </Box>

          {/* Filters */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              {/* Search Filter */}
              <TextField
                label="Search"
                variant="outlined"
                size="small"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Search by event type, endpoint, or user..."
                sx={{ flexGrow: 1, minWidth: 250 }}
              />

              {/* Event Type Filter */}
              <TextField
                select
                label="Event Type"
                variant="outlined"
                size="small"
                value={eventTypeFilter}
                onChange={(e) => setEventTypeFilter(e.target.value)}
                sx={{ minWidth: 200 }}
              >
                {eventTypes.map(type => (
                  <MenuItem key={type} value={type}>
                    {type === 'all' ? 'All Events' : type.replace(/_/g, ' ').toUpperCase()}
                  </MenuItem>
                ))}
              </TextField>

              {/* Refresh Button */}
              <Tooltip title="Refresh logs">
                <IconButton 
                  color="primary" 
                  onClick={fetchAuditLogs}
                  disabled={isLoading}
                >
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            </Box>

            {/* Stats */}
            <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                Showing {filteredLogs.length} of {logs.length} events
              </Typography>
            </Box>          </Paper>

          {/* Error State */}
          {error && (
            <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
              <Typography variant="body2" fontWeight="medium">
                Error loading audit logs
              </Typography>
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                {error}
              </Typography>
            </Alert>
          )}

          {/* Loading State */}
          {isLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <Box sx={{ textAlign: 'center' }}>
                <CircularProgress />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  Loading audit logs...
                </Typography>
              </Box>
            </Box>
          )}

          {/* Audit Logs Table */}
          {!isLoading && !error && (
            <>
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Timestamp</TableCell>
                    <TableCell>Event</TableCell>
                    <TableCell>User ID</TableCell>
                    <TableCell>Endpoint</TableCell>
                    <TableCell>IP Address</TableCell>
                    <TableCell align="center">Status</TableCell>
                    <TableCell align="right">Duration</TableCell>
                    <TableCell align="center">Details</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredLogs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} align="center" sx={{ py: 8 }}>
                        <Typography variant="body2" color="text.secondary">
                          No audit logs found
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : (
                    paginatedLogs.map((log) => (
                      <TableRow key={log.id} hover>
                        <TableCell>
                          <Typography variant="body2">
                            {new Date(log.timestamp).toLocaleString()}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            icon={getEventIcon(log.event_type)}
                            label={log.event_type.replace(/_/g, ' ')}
                            color={getEventColor(log.event_type)}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          {log.user_id ? (
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                              {log.user_id.substring(0, 12)}...
                            </Typography>
                          ) : (
                            <Typography variant="body2" color="text.secondary">
                              -
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          {log.endpoint ? (
                            <Chip
                              label={log.endpoint}
                              size="small"
                              variant="outlined"
                              sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}
                            />
                          ) : (
                            <Typography variant="body2" color="text.secondary">
                              -
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {log.ip_address || '-'}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          {log.response_status ? (
                            <Chip
                              label={log.response_status}
                              color={getStatusColor(log.response_status)}
                              size="small"
                            />
                          ) : (
                            <Typography variant="body2" color="text.secondary">
                              -
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell align="right">
                          {log.duration_ms ? (
                            <Typography variant="body2">
                              {log.duration_ms}ms
                            </Typography>
                          ) : (
                            <Typography variant="body2" color="text.secondary">
                              -
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell align="center">
                          <Tooltip title="View details">
                            <IconButton
                              size="small"
                              onClick={() => openDetailsDialog(log)}
                              color="primary"
                            >
                              <VisibilityIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              rowsPerPageOptions={[10, 25, 50, 100]}
              component="div"
              count={filteredLogs.length}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={handleChangePage}
              onRowsPerPageChange={handleChangeRowsPerPage}
            />
            </>
          )}

          {/* Details Dialog */}
          <Dialog
            open={detailsDialogOpen}
            onClose={closeDetailsDialog}
            maxWidth="md"
            fullWidth
          >
            <DialogTitle>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                {selectedLog && getEventIcon(selectedLog.event_type)}
                <Typography variant="h6">
                  Audit Log Details
                </Typography>
              </Box>
            </DialogTitle>
            <DialogContent>
              {selectedLog && (
                <Box sx={{ mt: 1 }}>
                  {/* Basic Info */}
                  <Accordion defaultExpanded>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        Basic Information
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                        <Box>
                          <Typography variant="body2" color="text.secondary">Event Type</Typography>
                          <Chip
                            icon={getEventIcon(selectedLog.event_type)}
                            label={selectedLog.event_type.replace(/_/g, ' ')}
                            color={getEventColor(selectedLog.event_type)}
                            size="small"
                            sx={{ mt: 0.5 }}
                          />
                        </Box>
                        <Box>
                          <Typography variant="body2" color="text.secondary">Timestamp</Typography>
                          <Typography variant="body2" sx={{ mt: 0.5 }}>
                            {new Date(selectedLog.timestamp).toLocaleString()}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="body2" color="text.secondary">User ID</Typography>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', mt: 0.5 }}>
                            {selectedLog.user_id || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="body2" color="text.secondary">Node ID</Typography>
                          <Typography variant="body2" sx={{ mt: 0.5 }}>
                            {selectedLog.node_id}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="body2" color="text.secondary">IP Address</Typography>
                          <Typography variant="body2" sx={{ mt: 0.5 }}>
                            {selectedLog.ip_address || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="body2" color="text.secondary">Response Status</Typography>
                          {selectedLog.response_status ? (
                            <Chip
                              label={selectedLog.response_status}
                              color={getStatusColor(selectedLog.response_status)}
                              size="small"
                              sx={{ mt: 0.5 }}
                            />
                          ) : (
                            <Typography variant="body2" sx={{ mt: 0.5 }}>-</Typography>
                          )}
                        </Box>
                        <Box>
                          <Typography variant="body2" color="text.secondary">Duration</Typography>
                          <Typography variant="body2" sx={{ mt: 0.5 }}>
                            {selectedLog.duration_ms ? `${selectedLog.duration_ms}ms` : '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="body2" color="text.secondary">Endpoint</Typography>
                          <Chip
                            label={selectedLog.endpoint || '-'}
                            size="small"
                            variant="outlined"
                            sx={{ fontFamily: 'monospace', fontSize: '0.7rem', mt: 0.5 }}
                          />
                        </Box>
                      </Box>
                    </AccordionDetails>
                  </Accordion>

                  {/* Request Details */}
                  {selectedLog.details?.request_details && (
                    <Accordion>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle1" fontWeight="bold">
                          Request Details
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Box sx={{ display: 'grid', gap: 2 }}>
                          {/* URL and Method */}
                          <Box>
                            <Typography variant="body2" color="text.secondary">Full URL</Typography>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', mt: 0.5, wordBreak: 'break-all' }}>
                              {selectedLog.details.request_details.url}
                            </Typography>
                          </Box>

                          {/* Query Parameters */}
                          {selectedLog.details.request_details.query_params && Object.keys(selectedLog.details.request_details.query_params).length > 0 && (
                            <Box>
                              <Typography variant="body2" color="text.secondary">Query Parameters</Typography>
                              <Paper sx={{ p: 2, mt: 0.5, bgcolor: 'grey.50' }}>
                                <pre style={{ margin: 0, fontSize: '0.875rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                  {JSON.stringify(selectedLog.details.request_details.query_params, null, 2)}
                                </pre>
                              </Paper>
                            </Box>
                          )}

                          {/* Request Body */}
                          {selectedLog.details.request_details.request_body && (
                            <Box>
                              <Typography variant="body2" color="text.secondary">Request Body</Typography>
                              <Paper sx={{ p: 2, mt: 0.5, bgcolor: 'grey.50' }}>
                                <pre style={{ margin: 0, fontSize: '0.875rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                  {typeof selectedLog.details.request_details.request_body === 'string' 
                                    ? selectedLog.details.request_details.request_body
                                    : JSON.stringify(selectedLog.details.request_details.request_body, null, 2)
                                  }
                                </pre>
                              </Paper>
                            </Box>
                          )}

                          {/* Headers */}
                          {selectedLog.details.request_details.headers && (
                            <Box>
                              <Typography variant="body2" color="text.secondary">Request Headers</Typography>
                              <Paper sx={{ p: 2, mt: 0.5, bgcolor: 'grey.50' }}>
                                <pre style={{ margin: 0, fontSize: '0.875rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                  {JSON.stringify(selectedLog.details.request_details.headers, null, 2)}
                                </pre>
                              </Paper>
                            </Box>
                          )}
                        </Box>
                      </AccordionDetails>
                    </Accordion>
                  )}

                  {/* Action Details */}
                  {selectedLog.details && Object.keys(selectedLog.details).filter(key => key !== 'request_details').length > 0 && (
                    <Accordion>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle1" fontWeight="bold">
                          Action Details
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                          <pre style={{ margin: 0, fontSize: '0.875rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                            {JSON.stringify(
                              Object.fromEntries(
                                Object.entries(selectedLog.details).filter(([key]) => key !== 'request_details')
                              ), 
                              null, 
                              2
                            )}
                          </pre>
                        </Paper>
                      </AccordionDetails>
                    </Accordion>
                  )}
                </Box>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={closeDetailsDialog}>Close</Button>
            </DialogActions>
          </Dialog>
        </Container>
      </Layout>
    </ProtectedRoute>
  );
}
