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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  CircularProgress,
  Alert,
  Chip,
  MenuItem,
  IconButton,
  Tooltip,
  Breadcrumbs,
  Link as MuiLink,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Delete as DeleteIcon,
  NavigateNext as NavigateNextIcon,
  ArrowUpward as ArrowUpwardIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import Layout from '@/components/Layout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';

interface Dataset {
  dataset_id: string;
  name: string;
  split: string;
  num_samples: number;
  num_normal: number;
  num_pneumonia: number;
  is_active?: boolean;
  created_at: string;
}

interface DirectoryItem {
  name: string;
  path: string;
  type: 'directory' | 'file';
  is_dataset?: boolean;
  num_samples?: number;
  num_normal?: number;
  num_pneumonia?: number;
}

interface BrowseResponse {
  current_directory: string;
  parent_directory: string | null;
  subdirectories: DirectoryItem[];
  files: DirectoryItem[];
}

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [browseDialogOpen, setBrowseDialogOpen] = useState(false);
  const [registering, setRegistering] = useState(false);
  const { token } = useAuth();
  
  // Browse state
  const [currentDirectory, setCurrentDirectory] = useState<string>('');
  const [browseData, setBrowseData] = useState<BrowseResponse | null>(null);
  const [browsing, setBrowsing] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string>('');
  const [datasetName, setDatasetName] = useState<string>('');
  const [split, setSplit] = useState('train');

  useEffect(() => {
    if (token) {
      fetchDatasets();
    }
  }, [token]);

  const fetchDatasets = async () => {
    try {
      setLoading(true);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const response = await fetch(`${apiBase}/api/data/list`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) throw new Error('Failed to fetch datasets');
      const data = await response.json();
      setDatasets(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const browseDirectory = async (path?: string) => {
    try {
      setBrowsing(true);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const url = path 
        ? `${apiBase}/api/data/browse?directory=${encodeURIComponent(path)}`
        : `${apiBase}/api/data/browse`;
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) throw new Error('Failed to browse directory');
      const data = await response.json();
      setBrowseData(data);
      setCurrentDirectory(data.current_directory);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Browse failed');
    } finally {
      setBrowsing(false);
    }
  };

  const handleOpenBrowse = () => {
    setBrowseDialogOpen(true);
    browseDirectory(); // Start at default directory
  };

  const handleSelectDataset = (item: DirectoryItem) => {
    if (item.is_dataset) {
      setSelectedPath(item.path);
      setDatasetName(item.name);
    }
  };

  const handleRegisterDataset = async () => {
    if (!selectedPath || !datasetName) return;

    try {
      setRegistering(true);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const response = await fetch(`${apiBase}/api/data/register`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          path: selectedPath,
          name: datasetName,
          split: split
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Registration failed');
      }

      setBrowseDialogOpen(false);
      setSelectedPath('');
      setDatasetName('');
      fetchDatasets();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setRegistering(false);
    }
  };

  const handleSetActive = async (datasetId: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const response = await fetch(`${apiBase}/api/data/set-active/${datasetId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error('Failed to set active dataset');

      fetchDatasets();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set active');
    }
  };

  const handleDelete = async (datasetId: string) => {
    if (!confirm('Unregister this dataset? (Files will be preserved on system)')) return;

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      const response = await fetch(`${apiBase}/api/data/${datasetId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error('Failed to delete dataset');

      fetchDatasets();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const activeDataset = datasets.find(d => d.is_active);

  return (
    <ProtectedRoute>
      <Layout title="Datasets">
      <Container maxWidth="lg">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4">
            Datasets
          </Typography>
          <Box>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={fetchDatasets}
              sx={{ mr: 1 }}
            >
              Refresh
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleOpenBrowse}
            >
              Register Dataset
            </Button>
          </Box>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Active Dataset Card */}
        {!loading && activeDataset && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CheckCircleIcon color="success" />
              Active Dataset
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">Name</Typography>
                <Typography variant="body1" fontWeight="bold">{activeDataset.name}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">Split</Typography>
                <Typography variant="body1">{activeDataset.split}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">Total Samples</Typography>
                <Typography variant="body1">{activeDataset.num_samples}</Typography>
              </Box>
            </Box>
          </Paper>
        )}

        {!loading && !activeDataset && (
          <Alert severity="info" sx={{ mb: 3 }}>
            No active dataset selected. Register and activate a dataset to use for training.
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
                  <TableCell>Name</TableCell>
                  <TableCell>Split</TableCell>
                  <TableCell align="right">Total Samples</TableCell>
                  <TableCell align="right">Normal</TableCell>
                  <TableCell align="right">Pneumonia</TableCell>
                  <TableCell>Created At</TableCell>
                  <TableCell align="center">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {datasets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography variant="body2" color="text.secondary">
                        No datasets registered. Browse and register a dataset from the hospital system.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  datasets.map((dataset) => (
                    <TableRow key={dataset.dataset_id} selected={dataset.is_active}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {dataset.name}
                          {dataset.is_active && (
                            <Chip label="Active" size="small" color="success" icon={<CheckCircleIcon />} />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip label={dataset.split} size="small" color="primary" />
                      </TableCell>
                      <TableCell align="right">{dataset.num_samples}</TableCell>
                      <TableCell align="right">{dataset.num_normal}</TableCell>
                      <TableCell align="right">{dataset.num_pneumonia}</TableCell>
                      <TableCell>
                        {new Date(dataset.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell align="center">
                        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
                          {!dataset.is_active && (
                            <Tooltip title="Set as Active">
                              <IconButton
                                size="small"
                                color="primary"
                                onClick={() => handleSetActive(dataset.dataset_id)}
                              >
                                <CheckCircleIcon />
                              </IconButton>
                            </Tooltip>
                          )}
                          <Tooltip title="Unregister">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleDelete(dataset.dataset_id)}
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Browse Dialog */}
        <Dialog open={browseDialogOpen} onClose={() => setBrowseDialogOpen(false)} maxWidth="md" fullWidth>
          <DialogTitle>Browse Hospital System for Datasets</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Browse the hospital filesystem to find and register existing datasets.
              Datasets must contain NORMAL and PNEUMONIA folders.
            </Typography>

            {/* Breadcrumbs */}
            {browseData && (
              <Box sx={{ mb: 2 }}>
                <Breadcrumbs separator={<NavigateNextIcon fontSize="small" />}>
                  <MuiLink
                    component="button"
                    variant="body2"
                    onClick={() => browseDirectory()}
                    sx={{ cursor: 'pointer' }}
                  >
                    Root
                  </MuiLink>
                  <Typography variant="body2" color="text.primary">
                    {currentDirectory.split('/').pop() || 'datasets'}
                  </Typography>
                </Breadcrumbs>
              </Box>
            )}

            {/* Directory Browser */}
            {browsing ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                <CircularProgress />
              </Box>
            ) : browseData ? (
              <Paper variant="outlined" sx={{ maxHeight: 400, overflow: 'auto', mb: 2 }}>
                <List>
                  {/* Parent directory */}
                  {browseData.parent_directory && (
                    <ListItem disablePadding>
                      <ListItemButton onClick={() => browseDirectory(browseData.parent_directory!)}>
                        <ListItemIcon>
                          <ArrowUpwardIcon />
                        </ListItemIcon>
                        <ListItemText primary=".." secondary="Parent directory" />
                      </ListItemButton>
                    </ListItem>
                  )}

                  {/* Subdirectories */}
                  {browseData.subdirectories.map((item) => (
                    <ListItem
                      key={item.path}
                      disablePadding
                      secondaryAction={
                        item.is_dataset && (
                          <Button
                            size="small"
                            variant={selectedPath === item.path ? 'contained' : 'outlined'}
                            onClick={() => handleSelectDataset(item)}
                          >
                            {selectedPath === item.path ? 'Selected' : 'Select'}
                          </Button>
                        )
                      }
                    >
                      <ListItemButton
                        onClick={() => !item.is_dataset && browseDirectory(item.path)}
                        selected={selectedPath === item.path}
                      >
                        <ListItemIcon>
                          {item.is_dataset ? <FolderOpenIcon color="primary" /> : <FolderIcon />}
                        </ListItemIcon>
                        <ListItemText
                          primary={item.name}
                          secondary={
                            item.is_dataset
                              ? `Dataset: ${item.num_samples} samples (${item.num_normal} normal, ${item.num_pneumonia} pneumonia)`
                              : 'Directory'
                          }
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}

                  {browseData.subdirectories.length === 0 && (
                    <ListItem>
                      <ListItemText
                        primary="No subdirectories"
                        secondary="This directory is empty or contains only files"
                      />
                    </ListItem>
                  )}
                </List>
              </Paper>
            ) : null}

            {/* Dataset Details */}
            {selectedPath && (
              <Box sx={{ mt: 2 }}>
                <TextField
                  fullWidth
                  label="Dataset Name"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <TextField
                  select
                  fullWidth
                  label="Split"
                  value={split}
                  onChange={(e) => setSplit(e.target.value)}
                >
                  <MenuItem value="train">Train</MenuItem>
                  <MenuItem value="val">Validation</MenuItem>
                  <MenuItem value="test">Test</MenuItem>
                </TextField>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setBrowseDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleRegisterDataset}
              variant="contained"
              disabled={!selectedPath || !datasetName || registering}
            >
              {registering ? <CircularProgress size={24} /> : 'Register Dataset'}
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Layout>
    </ProtectedRoute>
  );
}
