'use client';
import { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Button,
  Box,
  TextField,
  MenuItem,
  CircularProgress,
  Alert,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import { PlayArrow as PlayArrowIcon } from '@mui/icons-material';
import Layout from '@/components/Layout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';

export default function TrainPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [modelName, setModelName] = useState('resnet18');
  const [numEpochs, setNumEpochs] = useState(10);
  const [batchSize, setBatchSize] = useState(32);
  const [learningRate, setLearningRate] = useState(0.001);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const { token } = useAuth();

  useEffect(() => {
    if (token) {
      fetchDatasets();
    }
  }, [token]);

  const fetchDatasets = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const response = await fetch(`${apiBase}/api/data/list`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) return;
      const data = await response.json();
      setDatasets(data);
    } catch (err) {
      // Ignore
    }
  };

  const handleStartTraining = async () => {
    if (!datasetId) {
      setError('Please select a dataset');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const response = await fetch(`${apiBase}/api/train/local`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          dataset_id: datasetId,
          model_name: modelName,
          num_epochs: numEpochs,
          batch_size: batchSize,
          learning_rate: learningRate,
        }),
      });

      if (!response.ok) throw new Error('Failed to start training');

      const data = await response.json();
      setJobId(data.job_id);
      setSuccess(`Training started! Job ID: ${data.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start training');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ProtectedRoute>
      <Layout title="Train">
      <Container maxWidth="lg">
        <Typography variant="h4" gutterBottom>
          Local Training
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item={true} xs={12} md={8}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Training Configuration
              </Typography>

              <TextField
                select
                fullWidth
                label="Dataset"
                value={datasetId}
                onChange={(e) => setDatasetId(e.target.value)}
                sx={{ mb: 2 }}
              >
                <MenuItem value="">Select a dataset</MenuItem>
                {datasets.map((ds) => (
                  <MenuItem key={ds.dataset_id} value={ds.dataset_id}>
                    {ds.name} ({ds.num_samples} samples)
                  </MenuItem>
                ))}
              </TextField>

              <TextField
                select
                fullWidth
                label="Model Architecture"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                sx={{ mb: 2 }}
              >
                <MenuItem value="resnet18">ResNet18</MenuItem>
                <MenuItem value="densenet121">DenseNet121</MenuItem>
                <MenuItem value="efficientnet_b0">EfficientNet-B0</MenuItem>
              </TextField>

              <Grid container spacing={2}>
                <Grid item={true} xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Epochs"
                    value={numEpochs}
                    onChange={(e) => setNumEpochs(parseInt(e.target.value))}
                  />
                </Grid>
                <Grid item={true} xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Batch Size"
                    value={batchSize}
                    onChange={(e) => setBatchSize(parseInt(e.target.value))}
                  />
                </Grid>
                <Grid item={true} xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Learning Rate"
                    value={learningRate}
                    onChange={(e) => setLearningRate(parseFloat(e.target.value))}
                    slotProps={{ htmlInput: { step: 0.0001 } }}
                  />
                </Grid>
              </Grid>

              <Box sx={{ mt: 3 }}>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleStartTraining}
                  disabled={!datasetId || loading}
                  fullWidth
                >
                  {loading ? <CircularProgress size={24} /> : 'Start Training'}
                </Button>
              </Box>
            </Paper>
          </Grid>

          <Grid item={true} xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Training Info
                </Typography>
                <Typography variant="body2" paragraph>
                  Local training will:
                </Typography>
                <Typography variant="body2" component="div">
                  • Load the selected dataset
                </Typography>
                <Typography variant="body2" component="div">
                  • Initialize the model with pretrained weights
                </Typography>
                <Typography variant="body2" component="div">
                  • Train for the specified number of epochs
                </Typography>
                <Typography variant="body2" component="div">
                  • Save the trained model as a candidate
                </Typography>
                <Typography variant="body2" component="div" sx={{ mt: 2 }}>
                  • You can promote the model to deployed in the Models page
                </Typography>
              </CardContent>
            </Card>

            {jobId && (
              <Card sx={{ mt: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Job Started
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Job ID:
                  </Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {jobId}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 2 }}>
                    Check the job status in the Dashboard or Models page.
                  </Typography>
                </CardContent>
              </Card>
            )}
          </Grid>
        </Grid>
      </Container>
    </Layout>
    </ProtectedRoute>
  );
}
