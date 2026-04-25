'use client';
import { useEffect, useState } from 'react';
import { 
  Box, 
  Container, 
  Grid, 
  Paper, 
  Typography, 
  Card, 
  CardContent,
  CircularProgress,
  Alert
} from '@mui/material';
import {
  Folder as FolderIcon,
  Psychology as PsychologyIcon,
  Hub as HubIcon,
  Storage as StorageIcon,
  Work as WorkIcon,
} from '@mui/icons-material';
import Link from 'next/link';
import Layout from '@/components/Layout';

export default function DashboardPage() {
  const [nodeStatus, setNodeStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchNodeStatus();
    const interval = setInterval(fetchNodeStatus, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const fetchNodeStatus = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/node/status`);
      if (!response.ok) throw new Error('Failed to fetch node status');
      const data = await response.json();
      setNodeStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="Dashboard" nodeId={nodeStatus?.node_id}>
      <Container maxWidth="lg">
          <Typography variant="h4" gutterBottom>
            Dashboard
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {/* Node Info */}
              <Paper sx={{ p: 2, mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Node Information
                </Typography>
                <Grid container spacing={2}>
                  <Grid item={true} xs={12} sm={6} md={3}>
                    <Typography variant="body2" color="text.secondary">
                      Node ID
                    </Typography>
                    <Typography variant="h6">
                      {nodeStatus?.node_id || 'N/A'}
                    </Typography>
                  </Grid>
                  <Grid item={true} xs={12} sm={6} md={3}>
                    <Typography variant="body2" color="text.secondary">
                      Device
                    </Typography>
                    <Typography variant="h6">
                      {nodeStatus?.device || 'N/A'}
                    </Typography>
                  </Grid>
                  <Grid item={true} xs={12} sm={6} md={3}>
                    <Typography variant="body2" color="text.secondary">
                      Storage
                    </Typography>
                    <Typography variant="h6">
                      {nodeStatus?.storage_root || 'N/A'}
                    </Typography>
                  </Grid>
                  <Grid item={true} xs={12} sm={6} md={3}>
                    <Typography variant="body2" color="text.secondary">
                      Central URL
                    </Typography>
                    <Typography variant="body2">
                      {nodeStatus?.central_url || 'N/A'}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>

              {/* Statistics Cards */}
              <Grid container spacing={3}>
                {/* Models */}
                <Grid item={true} xs={12} md={4}>
                  <Card>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Models
                      </Typography>
                      <Typography variant="h4">
                        {nodeStatus?.models ? 
                          Object.values(nodeStatus.models).reduce((a: any, b: any) => a + b, 0) : 0}
                      </Typography>
                      <Box sx={{ mt: 2 }}>
                        <Typography variant="body2">
                          Candidate: {nodeStatus?.models?.candidate || 0}
                        </Typography>
                        <Typography variant="body2">
                          Deployed: {nodeStatus?.models?.deployed || 0}
                        </Typography>
                        <Typography variant="body2">
                          Archived: {nodeStatus?.models?.archived || 0}
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>

                {/* Jobs */}
                <Grid item={true} xs={12} md={4}>
                  <Card>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Jobs
                      </Typography>
                      <Typography variant="h4">
                        {nodeStatus?.jobs ? 
                          Object.values(nodeStatus.jobs).reduce((a: any, b: any) => a + b, 0) : 0}
                      </Typography>
                      <Box sx={{ mt: 2 }}>
                        <Typography variant="body2">
                          Pending: {nodeStatus?.jobs?.pending || 0}
                        </Typography>
                        <Typography variant="body2">
                          Running: {nodeStatus?.jobs?.running || 0}
                        </Typography>
                        <Typography variant="body2">
                          Completed: {nodeStatus?.jobs?.completed || 0}
                        </Typography>
                        <Typography variant="body2">
                          Failed: {nodeStatus?.jobs?.failed || 0}
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>

                {/* Datasets */}
                <Grid item={true} xs={12} md={4}>
                  <Card>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Datasets
                      </Typography>
                      <Typography variant="h4">
                        {nodeStatus?.datasets || 0}
                      </Typography>
                      <Box sx={{ mt: 2 }}>
                        <Typography variant="body2" color="text.secondary">
                          Total datasets available
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>

              {/* Quick Actions */}
              <Paper sx={{ p: 2, mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Quick Actions
                </Typography>
                <Grid container spacing={2}>
                  <Grid item={true}>
                    <Link href="/datasets" style={{ textDecoration: 'none' }}>
                      <Card sx={{ minWidth: 150, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
                        <CardContent>
                          <FolderIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                          <Typography variant="body1" sx={{ mt: 1 }}>
                            Datasets
                          </Typography>
                        </CardContent>
                      </Card>
                    </Link>
                  </Grid>
                  <Grid item={true}>
                    <Link href="/federated" style={{ textDecoration: 'none' }}>
                      <Card sx={{ minWidth: 150, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
                        <CardContent>
                          <HubIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                          <Typography variant="body1" sx={{ mt: 1 }}>
                            Federated
                          </Typography>
                        </CardContent>
                      </Card>
                    </Link>
                  </Grid>
                  <Grid item={true}>
                    <Link href="/models" style={{ textDecoration: 'none' }}>
                      <Card sx={{ minWidth: 150, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
                        <CardContent>
                          <StorageIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                          <Typography variant="body1" sx={{ mt: 1 }}>
                            Models
                          </Typography>
                        </CardContent>
                      </Card>
                    </Link>
                  </Grid>
                  <Grid item={true}>
                    <Link href="/inference" style={{ textDecoration: 'none' }}>
                      <Card sx={{ minWidth: 150, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
                        <CardContent>
                          <PsychologyIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                          <Typography variant="body1" sx={{ mt: 1 }}>
                            Inference
                          </Typography>
                        </CardContent>
                      </Card>
                    </Link>
                  </Grid>
                  <Grid item={true}>
                    <Link href="/jobs" style={{ textDecoration: 'none' }}>
                      <Card sx={{ minWidth: 150, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
                        <CardContent>
                          <WorkIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                          <Typography variant="body1" sx={{ mt: 1 }}>
                            Jobs
                          </Typography>
                        </CardContent>
                      </Card>
                    </Link>
                  </Grid>
                </Grid>
              </Paper>
            </>
          )}
        </Container>
    </Layout>
  );
}
