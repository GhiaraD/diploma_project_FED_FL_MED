'use client';
import { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Box,
  CircularProgress,
  Alert,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import Layout from '@/components/Layout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';

interface Model {
  model_id: string;
  model_name: string;
  version: string;
  type: string;
  labels: string[];
  round_id: string | null;
  metrics: any;
  created_at: string;
}

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [promoting, setPromoting] = useState<string | null>(null);
  const { token } = useAuth();

  useEffect(() => {
    if (token) {
      fetchModels();
    }
  }, [token]);

  const fetchModels = async () => {
    try {
      setLoading(true);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const response = await fetch(`${apiBase}/api/models/registry`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) throw new Error('Failed to fetch models');
      const data = await response.json();
      
      // Sort models by created_at (descending - newest first)
      const sortedModels = (data.models || []).sort((a: Model, b: Model) => {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
      
      setModels(sortedModels);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handlePromote = async (modelId: string) => {
    try {
      setPromoting(modelId);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const response = await fetch(`${apiBase}/api/models/promote`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ model_id: modelId }),
      });

      if (!response.ok) throw new Error('Failed to promote model');

      fetchModels();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Promotion failed');
    } finally {
      setPromoting(null);
    }
  };

  const getLabelColor = (label: string) => {
    switch (label) {
      case 'active':
        return 'success';
      case 'global':
        return 'primary';
      case 'candidate':
        return 'warning';
      default:
        return 'default';
    }
  };

  // Get active model
  const activeModel = models.find(m => m.labels?.includes('active'));

  return (
    <ProtectedRoute>
      <Layout title="Models">
      <Container maxWidth="lg">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4">
            Model Registry
          </Typography>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchModels}
          >
            Refresh
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Active Model Card */}
        {!loading && activeModel && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <CheckCircleIcon color="success" />
              Active Model
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 3 }}>
              {/* Column 1 */}
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}>
                  Model ID
                </Typography>
                <Typography variant="body1" sx={{ fontFamily: 'monospace', fontSize: '0.95rem', mb: 2 }}>
                  {activeModel.model_id}
                </Typography>
                
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}>
                  Architecture
                </Typography>
                <Typography variant="body1" fontWeight="bold" sx={{ mb: 2 }}>
                  {activeModel.model_name}
                </Typography>
              </Box>

              {/* Column 2 */}
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}>
                  Version
                </Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {activeModel.version}
                </Typography>
                
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}>
                  Created
                </Typography>
                <Typography variant="body1">
                  {new Date(activeModel.created_at).toLocaleString()}
                </Typography>
              </Box>

              {/* Column 3 */}
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}>
                  Accuracy
                </Typography>
                <Typography variant="h6" color="success.dark" fontWeight="bold" sx={{ mb: 2 }}>
                  {activeModel.metrics?.accuracy 
                    ? (activeModel.metrics.accuracy * 100).toFixed(2) + '%'
                    : 'N/A'}
                </Typography>
                
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}>
                  Labels
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {activeModel.labels.map((label) => (
                    <Chip
                      key={label}
                      label={label}
                      size="small"
                      color={getLabelColor(label) as any}
                    />
                  ))}
                </Box>
              </Box>
            </Box>
          </Paper>
        )}

        {!loading && !activeModel && (
          <Alert severity="info" sx={{ mb: 3 }}>
            No active model deployed. Promote a model to use it for inference.
          </Alert>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Model ID</TableCell>
                  <TableCell>Architecture</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell>Labels</TableCell>
                  <TableCell>Round ID</TableCell>
                  <TableCell>Accuracy</TableCell>
                  <TableCell>Created At</TableCell>
                  <TableCell align="center">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {models.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      <Typography variant="body2" color="text.secondary">
                        No models found. Train a model to get started.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  models.map((model) => (
                    <TableRow key={model.model_id}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                          {model.model_id}
                        </Typography>
                      </TableCell>
                      <TableCell>{model.model_name}</TableCell>
                      <TableCell>{model.version}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                          {(model.labels || []).map((label) => (
                            <Chip
                              key={label}
                              label={label}
                              size="small"
                              color={getLabelColor(label) as any}
                            />
                          ))}
                        </Box>
                      </TableCell>
                      <TableCell>
                        {model.round_id || '-'}
                      </TableCell>
                      <TableCell>
                        {model.metrics?.accuracy 
                          ? (model.metrics.accuracy * 100).toFixed(2) + '%'
                          : '-'}
                      </TableCell>
                      <TableCell>
                        {new Date(model.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell align="center">
                        {!model.labels?.includes('active') && (
                          <Tooltip title="Promote to Active">
                            <IconButton
                              size="small"
                              color="primary"
                              onClick={() => handlePromote(model.model_id)}
                              disabled={promoting === model.model_id}
                            >
                              {promoting === model.model_id ? (
                                <CircularProgress size={20} />
                              ) : (
                                <CheckCircleIcon />
                              )}
                            </IconButton>
                          </Tooltip>
                        )}
                        {model.labels?.includes('active') && (
                          <Chip label="In Use" size="small" color="success" icon={<CheckCircleIcon />} />
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Legend */}
        <Paper sx={{ p: 2, mt: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Model Labels:
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, mb: 1 }}>
            <Chip label="active" size="small" color="success" />
            <Typography variant="body2" sx={{ alignSelf: 'center' }}>
              - Currently deployed model used for inference
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2, mb: 1 }}>
            <Chip label="global" size="small" color="primary" />
            <Typography variant="body2" sx={{ alignSelf: 'center' }}>
              - Best model (highest accuracy)
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Chip label="candidate" size="small" color="warning" />
            <Typography variant="body2" sx={{ alignSelf: 'center' }}>
              - Models available for promotion
            </Typography>
          </Box>
        </Paper>
      </Container>
    </Layout>
    </ProtectedRoute>
  );
}
