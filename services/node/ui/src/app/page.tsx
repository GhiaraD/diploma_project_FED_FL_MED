'use client';
import { useEffect, useState } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography,
  CircularProgress,
  Alert,
  Container,
} from '@mui/material';
import Layout from '@/components/Layout';
import ProtectedRoute from '@/components/ProtectedRoute';
import SectionHeader from '@/components/SectionHeader';
import JobsTable from '@/components/JobsTable';
import MetricsCards from '@/components/MetricsCards';
import { useAuth } from '@/contexts/AuthContext';
import { API_BASE } from '@/config/api';
import type { Job, Model } from '@/types';

interface NodeData {
  healthy: boolean;
  uptime_sec: number;
  disk: {
    used_gb: number;
    total_gb: number;
  };
}

export default function DashboardPage() {
  const [node, setNode] = useState<NodeData>({ healthy: true, uptime_sec: 0, disk: { used_gb: 0, total_gb: 0 } });
  const [nodeStatus, setNodeStatus] = useState<any>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [fedRounds, setFedRounds] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { token, user } = useAuth();

  useEffect(() => {
    if (token) {
      fetchDashboardData();
      const interval = setInterval(fetchDashboardData, 10000);
      return () => clearInterval(interval);
    }
  }, [token]);

  const fetchDashboardData = async () => {
    try {
      const apiBase = API_BASE;
      
      // Fetch node status
      const statusResponse = await fetch(`${apiBase}/api/node/status`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        setNodeStatus(statusData);
        setNode({
          healthy: statusData.healthy || true,
          uptime_sec: statusData.uptime_seconds || 0,
          disk: { 
            used_gb: statusData.disk_used_gb || 0, 
            total_gb: statusData.disk_total_gb || 0 
          }
        });
      }

      // Fetch models
      try {
        const modelsResponse = await fetch(`${apiBase}/api/models/registry`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (modelsResponse.ok) {
          const modelsData = await modelsResponse.json();
          // API returns object with models array
          const modelsList = Array.isArray(modelsData) ? modelsData : (modelsData.models || []);
          setModels(modelsList);
        }
      } catch (err) {
        console.error('Failed to fetch models:', err);
      }

      // Fetch recent jobs
      try {
        const jobsResponse = await fetch(`${apiBase}/api/jobs/list?limit=5`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (jobsResponse.ok) {
          const jobsData = await jobsResponse.json();
          // API returns object with jobs array
          const jobsList = Array.isArray(jobsData) ? jobsData : (jobsData.jobs || []);
          setJobs(jobsList.slice(0, 5));
        }
      } catch (err) {
        console.error('Failed to fetch recent jobs:', err);
      }

      // Fetch federated rounds history
      try {
        const fedResponse = await fetch(`${apiBase}/api/federated/history`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (fedResponse.ok) {
          const fedData = await fedResponse.json();
          // API returns { total_rounds: number, rounds: array }
          if (fedData.rounds && Array.isArray(fedData.rounds) && fedData.rounds.length > 0) {
            setFedRounds(fedData.rounds);
          } else {
            setFedRounds([]);
          }
        }
      } catch (err) {
        console.error('Failed to fetch federated history:', err);
        setFedRounds([]);
      }

      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const deployed = Array.isArray(models) ? models.find(m => m.type === 'deployed') : null;
  const lastRound = Array.isArray(fedRounds) && fedRounds.length > 0 ? fedRounds[0] : null;

  return (
    <ProtectedRoute>
      <Layout nodeId={user?.node_id}>
        <Container maxWidth="lg" sx={{ py: 4 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Box>
              <SectionHeader 
                title="Dashboard" 
                subtitle="Node status, deployed model, and recent activity." 
              />

              {/* Top 3 Cards */}
              <Box 
                sx={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', 
                  gap: 2, 
                  mb: 2 
                }}
              >
                <Card sx={{ borderRadius: 3 }}>
                  <CardContent>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                      Node Health
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 800, mt: 0.5 }}>
                      {node.healthy ? 'Healthy' : 'Down'}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary' }}>
                      Uptime: {Math.floor(node.uptime_sec / 3600)}h • Disk: {node.disk.used_gb}/{node.disk.total_gb} GB
                    </Typography>
                  </CardContent>
                </Card>

                <Card sx={{ borderRadius: 3 }}>
                  <CardContent>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                      Deployed Model
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 800, mt: 0.5 }}>
                      {deployed ? `${deployed.model_name} ${deployed.version}` : 'None'}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary' }}>
                      {deployed ? '' : 'Promote a candidate model to deploy.'}
                    </Typography>
                  </CardContent>
                </Card>

                <Card sx={{ borderRadius: 3 }}>
                  <CardContent>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                      Federated
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 800, mt: 0.5 }}>
                      {lastRound ? lastRound.job_id : 'No sessions yet'}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary' }}>
                      {lastRound ? `Status: ${lastRound.local_status}` : 'Pull a plan to start.'}
                    </Typography>
                  </CardContent>
                </Card>
              </Box>

              {/* Key Metrics */}
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
                  Key metrics (deployed model)
                </Typography>
                <MetricsCards metrics={deployed?.metrics} />
              </Box>

              {/* Statistics Cards */}
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
                  Node statistics
                </Typography>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                    gap: 2,
                  }}
                >
                  {/* Models Card */}
                  <Card sx={{ borderRadius: 3 }}>
                    <CardContent>
                      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1, fontWeight: 600 }}>
                        Models
                      </Typography>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.2 }}>Candidate</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            {nodeStatus?.models?.candidate || 0}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.2 }}>Deployed</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            {nodeStatus?.models?.deployed || 0}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.2 }}>Archived</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            {nodeStatus?.models?.archived || 0}
                          </Typography>
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>

                  {/* Jobs Card */}
                  <Card sx={{ borderRadius: 3 }}>
                    <CardContent>
                      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1, fontWeight: 600 }}>
                        Jobs
                      </Typography>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.2 }}>Pending</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            {nodeStatus?.jobs?.pending || 0}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.2 }}>Running</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            {nodeStatus?.jobs?.running || 0}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.2 }}>Completed</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            {nodeStatus?.jobs?.completed || 0}
                          </Typography>
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>

                  {/* Datasets Card */}
                  <Card sx={{ borderRadius: 3 }}>
                    <CardContent>
                      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1, fontWeight: 600 }}>
                        Datasets
                      </Typography>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.2 }}>Total datasets</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            {nodeStatus?.datasets || 0}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.2 }}>Active</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            {nodeStatus?.active_datasets || 0}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '32px' }}>
                          <Typography variant="body2" sx={{ color: 'transparent', lineHeight: 1.2 }}>-</Typography>
                          <Typography variant="h6" sx={{ fontWeight: 700, color: 'transparent', lineHeight: 1.2 }}>
                            0
                          </Typography>
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                </Box>
              </Box>

              {/* Recent Jobs */}
              <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
                Recent jobs
              </Typography>
              <JobsTable jobs={jobs} />
            </Box>
          )}
        </Container>
      </Layout>
    </ProtectedRoute>
  );
}
