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
  Archive as ArchiveIcon,
} from '@mui/icons-material';
import Layout from '@/components/Layout';

interface Model {
  model_id: string;
  model_name: string;
  version: string;
  type: string;
  round_id: string | null;
  metrics: any;
  created_at: string;
}

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [promoting, setPromoting] = useState<string | null>(null);

  useEffect(() => {
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      setLoading(true);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/models/registry`);
      if (!response.ok) throw new Error('Failed to fetch models');
      const data = await response.json();
      setModels(data.models || []);
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
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/models/promote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'deployed':
        return 'success';
      case 'candidate':
        return 'warning';
      case 'archived':
        return 'default';
      default:
        return 'default';
    }
  };

  return (
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
                  <TableCell>Type</TableCell>
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
                        <Chip
                          label={model.type}
                          size="small"
                          color={getTypeColor(model.type) as any}
                        />
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
                        {model.type === 'candidate' && (
                          <Tooltip title="Promote to Deployed">
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
                        {model.type === 'deployed' && (
                          <Chip label="Active" size="small" color="success" icon={<CheckCircleIcon />} />
                        )}
                        {model.type === 'archived' && (
                          <ArchiveIcon fontSize="small" color="disabled" />
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
            Model Types:
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Chip label="Candidate" size="small" color="warning" />
            <Typography variant="body2" sx={{ alignSelf: 'center' }}>
              - Newly trained models awaiting promotion
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
            <Chip label="Deployed" size="small" color="success" />
            <Typography variant="body2" sx={{ alignSelf: 'center' }}>
              - Active model used for inference
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
            <Chip label="Archived" size="small" />
            <Typography variant="body2" sx={{ alignSelf: 'center' }}>
              - Previous versions no longer in use
            </Typography>
          </Box>
        </Paper>
      </Container>
    </Layout>
  );
}
