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
} from '@mui/material';
import { Upload as UploadIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import Layout from '@/components/Layout';

interface Dataset {
  dataset_id: string;
  name: string;
  split: string;
  num_samples: number;
  num_normal: number;
  num_pneumonia: number;
  created_at: string;
}

export default function StudiesPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [split, setSplit] = useState('train');

  useEffect(() => {
    fetchDatasets();
  }, []);

  const fetchDatasets = async () => {
    try {
      setLoading(true);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/data/list`);
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

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      setUploading(true);
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('split', split);

      const response = await fetch(`${apiBase}/api/data/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Upload failed');

      setUploadDialogOpen(false);
      setSelectedFile(null);
      fetchDatasets();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Layout title="Studies">
      <Container maxWidth="lg">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4">
            Studies & Datasets
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
              startIcon={<UploadIcon />}
              onClick={() => setUploadDialogOpen(true)}
            >
              Upload Dataset
            </Button>
          </Box>
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
                  <TableCell>Dataset ID</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Split</TableCell>
                  <TableCell align="right">Total Samples</TableCell>
                  <TableCell align="right">Normal</TableCell>
                  <TableCell align="right">Pneumonia</TableCell>
                  <TableCell>Created At</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {datasets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography variant="body2" color="text.secondary">
                        No datasets found. Upload a dataset to get started.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  datasets.map((dataset) => (
                    <TableRow key={dataset.dataset_id}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                          {dataset.dataset_id}
                        </Typography>
                      </TableCell>
                      <TableCell>{dataset.name}</TableCell>
                      <TableCell>
                        <Chip label={dataset.split} size="small" color="primary" />
                      </TableCell>
                      <TableCell align="right">{dataset.num_samples}</TableCell>
                      <TableCell align="right">{dataset.num_normal}</TableCell>
                      <TableCell align="right">{dataset.num_pneumonia}</TableCell>
                      <TableCell>
                        {new Date(dataset.created_at).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Upload Dialog */}
        <Dialog open={uploadDialogOpen} onClose={() => setUploadDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Upload Dataset</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Upload a ZIP file containing NORMAL and PNEUMONIA folders with chest X-ray images.
            </Typography>
            <TextField
              select
              fullWidth
              label="Split"
              value={split}
              onChange={(e) => setSplit(e.target.value)}
              sx={{ mb: 2 }}
            >
              <MenuItem value="train">Train</MenuItem>
              <MenuItem value="val">Validation</MenuItem>
              <MenuItem value="test">Test</MenuItem>
            </TextField>
            <Button
              variant="outlined"
              component="label"
              fullWidth
            >
              {selectedFile ? selectedFile.name : 'Choose ZIP File'}
              <input
                type="file"
                hidden
                accept=".zip"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              />
            </Button>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setUploadDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleUpload}
              variant="contained"
              disabled={!selectedFile || uploading}
            >
              {uploading ? <CircularProgress size={24} /> : 'Upload'}
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Layout>
  );
}
