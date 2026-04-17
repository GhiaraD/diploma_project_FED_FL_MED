'use client';
import { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Button,
  Box,
  TextField,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  Grid,
  Stepper,
  Step,
  StepLabel,
  Chip,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import {
  Hub as HubIcon,
  PlayArrow as PlayArrowIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import Layout from '@/components/Layout';

const steps = ['Join Round', 'Download Model', 'Train Locally', 'Submit Update', 'Aggregation'];

export default function FederatedPage() {
  const [roundId, setRoundId] = useState('');
  const [datasetId, setDatasetId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [roundStatus, setRoundStatus] = useState<any>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<any>(null);

  useEffect(() => {
    if (roundId) {
      fetchRoundStatus();
      const interval = setInterval(fetchRoundStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [roundId]);

  useEffect(() => {
    if (jobId) {
      fetchJobStatus();
      const interval = setInterval(fetchJobStatus, 3000);
      return () => clearInterval(interval);
    }
  }, [jobId]);

  const fetchRoundStatus = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/federated/status/${roundId}`);
      if (!response.ok) return;
      const data = await response.json();
      setRoundStatus(data);
    } catch (err) {
      // Ignore errors for polling
    }
  };

  const fetchJobStatus = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/train/status/${jobId}`);
      if (!response.ok) return;
      const data = await response.json();
      setJobStatus(data);
    } catch (err) {
      // Ignore errors for polling
    }
  };

  const handleJoinRound = async () => {
    try {
      setLoading(true);
      setError(null);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/federated/join/${roundId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (!response.ok) throw new Error('Failed to join round');

      setSuccess(`Successfully joined round ${roundId}`);
      fetchRoundStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join round');
    } finally {
      setLoading(false);
    }
  };

  const handleStartTraining = async () => {
    if (!datasetId) {
      setError('Please enter a dataset ID');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(
        `${apiBase}/api/federated/train/${roundId}?dataset_id=${datasetId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      );

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

  const getCurrentStep = () => {
    if (!roundStatus) return 0;
    if (roundStatus.local_status === 'not_started') return 0;
    if (roundStatus.local_status === 'pending') return 1;
    if (roundStatus.local_status === 'running') return 2;
    if (roundStatus.local_status === 'completed') return 4;
    return 0;
  };

  return (
    <Layout title="Federated Learning">
      <Container maxWidth="lg">
        <Typography variant="h4" gutterBottom>
          Federated Learning
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

        {/* Join Round */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Join FL Round
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
            <TextField
              label="Round ID"
              value={roundId}
              onChange={(e) => setRoundId(e.target.value)}
              placeholder="e.g., R-1"
              sx={{ flexGrow: 1 }}
            />
            <Button
              variant="contained"
              startIcon={<HubIcon />}
              onClick={handleJoinRound}
              disabled={!roundId || loading}
            >
              Join Round
            </Button>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={fetchRoundStatus}
              disabled={!roundId}
            >
              Refresh
            </Button>
          </Box>
        </Paper>

        {/* Round Status */}
        {roundStatus && (
          <>
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Round Status
              </Typography>
              <Grid container spacing={2}>
                <Grid item={true} xs={12} md={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Round ID
                      </Typography>
                      <Typography variant="h6">{roundStatus.round_id}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item={true} xs={12} md={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Local Status
                      </Typography>
                      <Chip
                        label={roundStatus.local_status}
                        color={
                          roundStatus.local_status === 'completed'
                            ? 'success'
                            : roundStatus.local_status === 'running'
                            ? 'primary'
                            : 'default'
                        }
                      />
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>

              {roundStatus.central_status && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Central Server Status:
                  </Typography>
                  <List dense>
                    <ListItem>
                      <ListItemText
                        primary="Participants"
                        secondary={roundStatus.central_status.participants?.join(', ') || 'N/A'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="Updates Received"
                        secondary={roundStatus.central_status.updates_received || 0}
                      />
                    </ListItem>
                  </List>
                </Box>
              )}
            </Paper>

            {/* Progress Stepper */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                FL Workflow Progress
              </Typography>
              <Stepper activeStep={getCurrentStep()} alternativeLabel>
                {steps.map((label) => (
                  <Step key={label}>
                    <StepLabel>{label}</StepLabel>
                  </Step>
                ))}
              </Stepper>
            </Paper>

            {/* Start Training */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Start Federated Training
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                <TextField
                  label="Dataset ID"
                  value={datasetId}
                  onChange={(e) => setDatasetId(e.target.value)}
                  placeholder="e.g., dataset_train_abc123"
                  sx={{ flexGrow: 1 }}
                  helperText="Enter the dataset ID from Studies page"
                />
                <Button
                  variant="contained"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleStartTraining}
                  disabled={!roundId || !datasetId || loading}
                >
                  Start Training
                </Button>
              </Box>
            </Paper>

            {/* Job Status */}
            {jobStatus && (
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Training Job Status
                </Typography>
                <Grid container spacing={2}>
                  <Grid item={true} xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">
                      Job ID
                    </Typography>
                    <Typography variant="body1" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                      {jobStatus.job_id}
                    </Typography>
                  </Grid>
                  <Grid item={true} xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">
                      Status
                    </Typography>
                    <Chip
                      label={jobStatus.status}
                      color={
                        jobStatus.status === 'completed'
                          ? 'success'
                          : jobStatus.status === 'running'
                          ? 'primary'
                          : jobStatus.status === 'failed'
                          ? 'error'
                          : 'default'
                      }
                    />
                  </Grid>
                  <Grid item={true} xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">
                      Created At
                    </Typography>
                    <Typography variant="body2">
                      {new Date(jobStatus.created_at).toLocaleString()}
                    </Typography>
                  </Grid>
                </Grid>

                {jobStatus.result && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Results:
                    </Typography>
                    <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', overflow: 'auto' }}>
                      {JSON.stringify(jobStatus.result, null, 2)}
                    </pre>
                  </Box>
                )}

                {jobStatus.error && (
                  <Alert severity="error" sx={{ mt: 2 }}>
                    {jobStatus.error}
                  </Alert>
                )}
              </Paper>
            )}
          </>
        )}

        {/* Instructions */}
        {!roundStatus && (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              How to Participate in Federated Learning
            </Typography>
            <Typography variant="body2" paragraph>
              1. Enter a Round ID (e.g., R-1) and click "Join Round"
            </Typography>
            <Typography variant="body2" paragraph>
              2. Upload a dataset in the Studies page if you haven't already
            </Typography>
            <Typography variant="body2" paragraph>
              3. Enter the Dataset ID and click "Start Training"
            </Typography>
            <Typography variant="body2" paragraph>
              4. Wait for training to complete (this may take several minutes)
            </Typography>
            <Typography variant="body2" paragraph>
              5. Your local model will be trained and delta updates will be sent to the central server
            </Typography>
            <Typography variant="body2">
              6. The central server will aggregate updates from all participants
            </Typography>
          </Paper>
        )}
      </Container>
    </Layout>
  );
}
