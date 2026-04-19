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
  Grid,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Checkbox,
  TextField,
  Divider,
  Slider,
  IconButton,
} from '@mui/material';
import { 
  Psychology as PsychologyIcon, 
  Folder as FolderIcon,
  Image as ImageIcon,
  Refresh as RefreshIcon,
  NavigateBefore as NavigateBeforeIcon,
  NavigateNext as NavigateNextIcon,
} from '@mui/icons-material';
import Layout from '@/components/Layout';

const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function InferencePage() {
  const [currentDir, setCurrentDir] = useState('/storage/datasets');
  const [files, setFiles] = useState<any[]>([]);
  const [subdirs, setSubdirs] = useState<any[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);
  
  // Viewer state
  const [selectedResultIndex, setSelectedResultIndex] = useState<number>(0);
  const [gradcamOpacity, setGradcamOpacity] = useState<number>(0.4);

  // Browse directory
  const browseDirectory = async (directory: string) => {
    try {
      setBrowsing(true);
      setError(null);
      
      const response = await fetch(
        `${apiBase}/api/infer/browse?directory=${encodeURIComponent(directory)}`
      );
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to browse directory');
      }
      
      const data = await response.json();
      setFiles(data.files || []);
      setSubdirs(data.subdirectories || []);
      setCurrentDir(directory);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to browse directory');
    } finally {
      setBrowsing(false);
    }
  };

  // Load initial directory
  useEffect(() => {
    browseDirectory(currentDir);
  }, []);

  // Toggle file selection
  const toggleFileSelection = (path: string) => {
    setSelectedPaths(prev => 
      prev.includes(path) 
        ? prev.filter(p => p !== path)
        : [...prev, path]
    );
  };

  // Run inference
  const handleInference = async () => {
    if (selectedPaths.length === 0) {
      setError('Please select at least one image');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setResults([]);
      
      // Start inference job
      const response = await fetch(`${apiBase}/api/infer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_paths: selectedPaths,
          generate_gradcam: true
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start inference');
      }
      
      const data = await response.json();
      setJobId(data.job_id);
      
      // Poll for results
      pollResults(data.job_id);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Inference failed');
      setLoading(false);
    }
  };

  // Poll for inference results
  const pollResults = async (jobId: string) => {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;
    
    const poll = setInterval(async () => {
      try {
        attempts++;
        
        const response = await fetch(`${apiBase}/api/infer/results/${jobId}`);
        const data = await response.json();
        
        if (data.status === 'completed') {
          clearInterval(poll);
          setResults(data.results || []);
          setSelectedResultIndex(0); // Select first result
          setLoading(false);
        } else if (data.status === 'failed') {
          clearInterval(poll);
          setError('Inference job failed');
          setLoading(false);
        } else if (attempts >= maxAttempts) {
          clearInterval(poll);
          setError('Inference timeout');
          setLoading(false);
        }
      } catch (err) {
        clearInterval(poll);
        setError('Failed to get results');
        setLoading(false);
      }
    }, 5000); // Poll every 5 seconds
  };

  return (
    <Layout title="Inference">
      <Container maxWidth="lg">
        <Typography variant="h4" gutterBottom>
          Inference & Grad-CAM
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* File Browser */}
          <Grid item={true} xs={12} md={results.length > 0 ? 6 : 8}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                  Browse Hospital Images
                </Typography>
                <Button
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={() => browseDirectory(currentDir)}
                  disabled={browsing}
                >
                  Refresh
                </Button>
              </Box>

              <TextField
                fullWidth
                size="small"
                label="Current Directory"
                value={currentDir}
                onChange={(e) => setCurrentDir(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    browseDirectory(currentDir);
                  }
                }}
                sx={{ mb: 2 }}
              />

              {browsing ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                  <CircularProgress />
                </Box>
              ) : (
                <>
                  {/* Subdirectories */}
                  {subdirs.length > 0 && (
                    <>
                      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        Folders
                      </Typography>
                      <List dense>
                        {subdirs.map((dir) => (
                          <ListItem key={dir.path} disablePadding>
                            <ListItemButton onClick={() => browseDirectory(dir.path)}>
                              <FolderIcon sx={{ mr: 1, color: 'primary.main' }} />
                              <ListItemText primary={dir.name} />
                            </ListItemButton>
                          </ListItem>
                        ))}
                      </List>
                      <Divider sx={{ my: 2 }} />
                    </>
                  )}

                  {/* Image Files */}
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Images ({files.length})
                  </Typography>
                  {files.length === 0 ? (
                    <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                      No images found in this directory
                    </Typography>
                  ) : (
                    <List dense sx={{ maxHeight: 400, overflow: 'auto' }}>
                      {files.map((file) => (
                        <ListItem key={file.path} disablePadding>
                          <ListItemButton onClick={() => toggleFileSelection(file.path)}>
                            <Checkbox
                              edge="start"
                              checked={selectedPaths.includes(file.path)}
                              tabIndex={-1}
                              disableRipple
                            />
                            <ImageIcon sx={{ mr: 1, color: 'text.secondary' }} />
                            <ListItemText 
                              primary={file.name}
                              secondary={`${(file.size / 1024).toFixed(1)} KB`}
                            />
                          </ListItemButton>
                        </ListItem>
                      ))}
                    </List>
                  )}
                </>
              )}

              <Box sx={{ mt: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Selected: {selectedPaths.length} image(s)
                </Typography>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<PsychologyIcon />}
                  onClick={handleInference}
                  disabled={selectedPaths.length === 0 || loading}
                  fullWidth
                >
                  {loading ? <CircularProgress size={24} /> : 'Run Inference'}
                </Button>
              </Box>
            </Paper>
          </Grid>

          {/* Results Viewer */}
          {results.length > 0 ? (
            <Grid item={true} xs={12} md={6}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Inference Results
                </Typography>

                {/* Result Navigation */}
                {results.length > 1 && (
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2 }}>
                    <IconButton 
                      onClick={() => setSelectedResultIndex(Math.max(0, selectedResultIndex - 1))}
                      disabled={selectedResultIndex === 0}
                    >
                      <NavigateBeforeIcon />
                    </IconButton>
                    <Typography variant="body2" sx={{ mx: 2 }}>
                      {selectedResultIndex + 1} / {results.length}
                    </Typography>
                    <IconButton 
                      onClick={() => setSelectedResultIndex(Math.min(results.length - 1, selectedResultIndex + 1))}
                      disabled={selectedResultIndex === results.length - 1}
                    >
                      <NavigateNextIcon />
                    </IconButton>
                  </Box>
                )}

                {/* Current Result */}
                {results[selectedResultIndex] && (
                  <>
                    {/* Prediction Info */}
                    <Card sx={{ mb: 2 }}>
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                          <Typography variant="subtitle2" color="text.secondary">
                            Prediction
                          </Typography>
                          <Chip
                            label={results[selectedResultIndex].predicted_class === 0 ? 'NORMAL' : 'PNEUMONIA'}
                            color={results[selectedResultIndex].predicted_class === 0 ? 'success' : 'error'}
                            size="small"
                          />
                        </Box>
                        <Typography variant="h4" gutterBottom>
                          {(results[selectedResultIndex].confidence * 100).toFixed(1)}%
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', wordBreak: 'break-all' }}>
                          {results[selectedResultIndex].image_path.split('/').pop()}
                        </Typography>
                      </CardContent>
                    </Card>

                    {/* Image Viewer with Grad-CAM Overlay */}
                    <Box sx={{ 
                      position: 'relative', 
                      width: '100%',
                      maxWidth: 400,
                      mx: 'auto',
                      mb: 2 
                    }}>
                      {/* Original Image */}
                      <Box
                        component="img"
                        src={`${apiBase}/api/infer/image?path=${encodeURIComponent(results[selectedResultIndex].image_path)}`}
                        alt="Original"
                        sx={{
                          width: '100%',
                          height: 'auto',
                          display: 'block',
                          borderRadius: 1,
                          border: '1px solid',
                          borderColor: 'divider',
                        }}
                      />
                      
                      {/* Grad-CAM Overlay */}
                      {results[selectedResultIndex].gradcam_path && (
                        <Box
                          component="img"
                          src={`${apiBase}/api/infer/image?path=${encodeURIComponent(results[selectedResultIndex].gradcam_path)}`}
                          alt="Grad-CAM"
                          sx={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '100%',
                            height: '100%',
                            opacity: gradcamOpacity,
                            borderRadius: 1,
                            pointerEvents: 'none',
                            transition: 'opacity 0.05s linear',
                          }}
                        />
                      )}
                    </Box>

                    {/* Opacity Slider */}
                    {results[selectedResultIndex].gradcam_path && (
                      <Box sx={{ px: 2, maxWidth: 400, mx: 'auto' }}>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Grad-CAM Opacity: {(gradcamOpacity * 100).toFixed(0)}%
                        </Typography>
                        <Slider
                          value={gradcamOpacity}
                          onChange={(_, value) => setGradcamOpacity(value as number)}
                          min={0}
                          max={1}
                          step={0.01}
                          marks={[
                            { value: 0, label: '0%' },
                            { value: 0.4, label: '40%' },
                            { value: 1, label: '100%' },
                          ]}
                          valueLabelDisplay="auto"
                          valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
                        />
                      </Box>
                    )}

                    {/* Probabilities */}
                    <Card sx={{ mt: 2 }}>
                      <CardContent>
                        <Typography variant="subtitle2" gutterBottom>
                          Class Probabilities
                        </Typography>
                        <Box sx={{ mt: 1 }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                            <Typography variant="body2">NORMAL</Typography>
                            <Typography variant="body2" fontWeight="bold">
                              {(results[selectedResultIndex].probabilities[0] * 100).toFixed(2)}%
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2">PNEUMONIA</Typography>
                            <Typography variant="body2" fontWeight="bold">
                              {(results[selectedResultIndex].probabilities[1] * 100).toFixed(2)}%
                            </Typography>
                          </Box>
                        </Box>
                      </CardContent>
                    </Card>
                  </>
                )}
              </Paper>
            </Grid>
          ) : (
            /* Info Panel (shown when no results) */
            <Grid item={true} xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    On-Premise Inference
                  </Typography>
                  <Typography variant="body2" paragraph>
                    This interface allows you to run inference on images that are already stored in the hospital's filesystem.
                  </Typography>
                  <Typography variant="body2" component="div">
                    • Images remain in their original location
                  </Typography>
                  <Typography variant="body2" component="div">
                    • No data leaves the hospital premises
                  </Typography>
                  <Typography variant="body2" component="div">
                    • Uses deployed model from registry
                  </Typography>
                  <Typography variant="body2" component="div">
                    • Generates Grad-CAM visualizations
                  </Typography>
                </CardContent>
              </Card>

              <Card sx={{ mt: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Grad-CAM
                  </Typography>
                  <Typography variant="body2">
                    Gradient-weighted Class Activation Mapping provides visual explanations
                    by highlighting the regions that were most important for the prediction.
                  </Typography>
                </CardContent>
              </Card>

              <Card sx={{ mt: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Available Directories
                  </Typography>
                  <Typography variant="body2" component="div">
                    • /storage/datasets
                  </Typography>
                  <Typography variant="body2" component="div">
                    • /hospital_data
                  </Typography>
                  <Typography variant="body2" component="div">
                    • /mnt/radiology
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          )}
        </Grid>
      </Container>
    </Layout>
  );
}
