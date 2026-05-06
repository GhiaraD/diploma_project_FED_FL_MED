'use client';
import { useState, useEffect, useRef, useMemo } from 'react';
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
} from '@mui/material';
import { 
  Psychology as PsychologyIcon, 
  Folder as FolderIcon,
  Image as ImageIcon,
  Refresh as RefreshIcon,
  NavigateBefore as NavigateBeforeIcon,
  NavigateNext as NavigateNextIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import Layout from '@/components/Layout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';

const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';

export default function InferencePage() {
  const { token } = useAuth();
  const [currentDir, setCurrentDir] = useState('/storage/datasets');
  const [files, setFiles] = useState<any[]>([]);
  const [subdirs, setSubdirs] = useState<any[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);
  
  // History state
  const [inferenceHistory, setInferenceHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyPage, setHistoryPage] = useState(0);
  const [historyRowsPerPage, setHistoryRowsPerPage] = useState(10);
  const [historySearchDate, setHistorySearchDate] = useState('');
  
  // Viewer state
  const [selectedResultIndex, setSelectedResultIndex] = useState<number>(0);
  const [gradcamOpacity, setGradcamOpacity] = useState<number>(0.4);
  const [gradcamEnabled, setGradcamEnabled] = useState<boolean>(true);
  
  // Image preloading refs
  const imageCache = useRef<Map<string, HTMLImageElement>>(new Map());
  const [imagesLoaded, setImagesLoaded] = useState<boolean>(false);

  // Preload images when results change
  useEffect(() => {
    if (results.length === 0) {
      setImagesLoaded(false);
      return;
    }

    const currentResult = results[selectedResultIndex];
    if (!currentResult) return;

    setImagesLoaded(false);
    
    const imagePath = currentResult.image_path;
    const gradcamPath = currentResult.gradcam_path;
    
    const imageUrl = `${apiBase}/api/infer/image?path=${encodeURIComponent(imagePath)}`;
    const gradcamUrl = gradcamPath ? `${apiBase}/api/infer/image?path=${encodeURIComponent(gradcamPath)}` : null;

    let loadedCount = 0;
    const totalImages = gradcamUrl ? 2 : 1;

    const checkAllLoaded = () => {
      loadedCount++;
      if (loadedCount === totalImages) {
        setImagesLoaded(true);
      }
    };

    // Preload main image
    if (!imageCache.current.has(imageUrl)) {
      const img = new Image();
      img.onload = () => {
        imageCache.current.set(imageUrl, img);
        checkAllLoaded();
      };
      img.onerror = () => checkAllLoaded();
      img.src = imageUrl;
    } else {
      checkAllLoaded();
    }

    // Preload gradcam image
    if (gradcamUrl) {
      if (!imageCache.current.has(gradcamUrl)) {
        const img = new Image();
        img.onload = () => {
          imageCache.current.set(gradcamUrl, img);
          checkAllLoaded();
        };
        img.onerror = () => checkAllLoaded();
        img.src = gradcamUrl;
      } else {
        checkAllLoaded();
      }
    }
  }, [results, selectedResultIndex, apiBase]);

  // Memoize image URLs to prevent recalculation
  const currentImageUrls = useMemo(() => {
    if (results.length === 0 || !results[selectedResultIndex]) {
      return { imageUrl: null, gradcamUrl: null };
    }
    
    const result = results[selectedResultIndex];
    return {
      imageUrl: `${apiBase}/api/infer/image?path=${encodeURIComponent(result.image_path)}`,
      gradcamUrl: result.gradcam_path 
        ? `${apiBase}/api/infer/image?path=${encodeURIComponent(result.gradcam_path)}`
        : null
    };
  }, [results, selectedResultIndex, apiBase]);

  // Browse directory
  const browseDirectory = async (directory: string) => {
    try {
      setBrowsing(true);
      setError(null);
      
      const response = await fetch(
        `${apiBase}/api/infer/browse?directory=${encodeURIComponent(directory)}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
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

  // Load initial directory and history
  useEffect(() => {
    if (token) {
      browseDirectory(currentDir);
      loadInferenceHistory();
    }
  }, [token]);

  // Load inference history
  const loadInferenceHistory = async () => {
    try {
      setLoadingHistory(true);
      const response = await fetch(`${apiBase}/api/jobs/list?job_type=infer&limit=100`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (!response.ok) throw new Error('Failed to load history');
      
      const data = await response.json();
      setInferenceHistory(data.jobs || []);
    } catch (err) {
      console.error('Failed to load inference history:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Load results from history
  const loadHistoryResults = async (historyJobId: string) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${apiBase}/api/infer/results/${historyJobId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      const data = await response.json();
      
      if (data.status === 'completed') {
        setResults(data.results || []);
        setSelectedResultIndex(0);
        setJobId(historyJobId);
      } else {
        setError(`Job status: ${data.status}`);
      }
    } catch (err) {
      setError('Failed to load results');
    } finally {
      setLoading(false);
    }
  };

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
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
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
      
      // Reload history to show new job
      loadInferenceHistory();
      
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
        
        const response = await fetch(`${apiBase}/api/infer/results/${jobId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
        const data = await response.json();
        
        if (data.status === 'completed') {
          clearInterval(poll);
          setResults(data.results || []);
          setSelectedResultIndex(0);
          setLoading(false);
          loadInferenceHistory(); // Refresh history
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

  // Filter history by date
  const filteredHistory = inferenceHistory.filter(job => {
    if (!historySearchDate) return true;
    const jobDate = new Date(job.created_at).toLocaleDateString();
    return jobDate.includes(historySearchDate);
  });

  // Paginated history
  const paginatedHistory = filteredHistory.slice(
    historyPage * historyRowsPerPage,
    historyPage * historyRowsPerPage + historyRowsPerPage
  );

  // Handle page change
  const handleChangePage = (event: unknown, newPage: number) => {
    setHistoryPage(newPage);
  };

  // Handle rows per page change
  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setHistoryRowsPerPage(parseInt(event.target.value, 10));
    setHistoryPage(0);
  };

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'running': return 'primary';
      case 'failed': return 'error';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  return (
    <ProtectedRoute>
      <Layout title="Inference">
      <Container maxWidth="xl">
        <Typography variant="h4" gutterBottom>
          Inference & Grad-CAM
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Top Section: Browse Images + Results Viewer */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          {/* Browse Images */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, height: '100%' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                  Browse Images
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
                      No images found
                    </Typography>
                  ) : (
                    <List dense sx={{ maxHeight: 300, overflow: 'auto' }}>
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
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, height: '100%' }}>
              <Typography variant="h6" gutterBottom>
                Results
              </Typography>

              {/* Result Navigation - Always visible when there are results */}
              {results.length > 0 && (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2 }}>
                  <IconButton 
                    onClick={() => setSelectedResultIndex(Math.max(0, selectedResultIndex - 1))}
                    disabled={selectedResultIndex === 0 || results.length <= 1}
                  >
                    <NavigateBeforeIcon />
                  </IconButton>
                  <Typography variant="body2" sx={{ mx: 2 }}>
                    {selectedResultIndex + 1} / {results.length}
                  </Typography>
                  <IconButton 
                    onClick={() => setSelectedResultIndex(Math.min(results.length - 1, selectedResultIndex + 1))}
                    disabled={selectedResultIndex === results.length - 1 || results.length <= 1}
                  >
                    <NavigateNextIcon />
                  </IconButton>
                </Box>
              )}

              {/* Results Display - Always show both columns */}
              <Grid container spacing={2}>
                {/* Left Column: Prediction & Probabilities */}
                <Grid item xs={12} md={6}>
                  {results.length > 0 && results[selectedResultIndex] ? (
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

                      {/* Probabilities */}
                      <Card>
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
                  ) : (
                    <>
                      {/* Empty Prediction Card */}
                      <Card sx={{ mb: 2 }}>
                        <CardContent>
                          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                            Prediction
                          </Typography>
                          <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                            -
                          </Typography>
                        </CardContent>
                      </Card>

                      {/* Empty Probabilities Card */}
                      <Card>
                        <CardContent>
                          <Typography variant="subtitle2" gutterBottom>
                            Class Probabilities
                          </Typography>
                          <Box sx={{ mt: 1 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                              <Typography variant="body2" color="text.secondary">NORMAL</Typography>
                              <Typography variant="body2" color="text.secondary">-</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                              <Typography variant="body2" color="text.secondary">PNEUMONIA</Typography>
                              <Typography variant="body2" color="text.secondary">-</Typography>
                            </Box>
                          </Box>
                        </CardContent>
                      </Card>
                    </>
                  )}
                </Grid>

                {/* Right Column: Image & Opacity */}
                <Grid item xs={12} md={6}>
                  {results.length > 0 && results[selectedResultIndex] ? (
                    <>
                      {/* Image Viewer with Grad-CAM Overlay */}
                      <Box sx={{ 
                        position: 'relative', 
                        width: '100%',
                        maxWidth: 400,
                        mx: 'auto',
                        mb: 2 
                      }}>
                        {/* Loading indicator */}
                        {!imagesLoaded && (
                          <Box sx={{
                            position: 'absolute',
                            top: '50%',
                            left: '50%',
                            transform: 'translate(-50%, -50%)',
                            zIndex: 10
                          }}>
                            <CircularProgress />
                          </Box>
                        )}
                        
                        {/* Original Image */}
                        <Box
                          component="img"
                          src={currentImageUrls.imageUrl || ''}
                          alt="Original"
                          sx={{
                            width: '100%',
                            height: 'auto',
                            display: 'block',
                            borderRadius: 1,
                            border: '1px solid',
                            borderColor: 'divider',
                            opacity: imagesLoaded ? 1 : 0.3,
                            transition: 'opacity 0.3s ease-in-out',
                          }}
                        />
                        
                        {/* Grad-CAM Overlay */}
                        {currentImageUrls.gradcamUrl && gradcamEnabled && (
                          <Box
                            component="img"
                            src={currentImageUrls.gradcamUrl}
                            alt="Grad-CAM"
                            sx={{
                              position: 'absolute',
                              top: 0,
                              left: 0,
                              width: '100%',
                              height: '100%',
                              opacity: imagesLoaded ? gradcamOpacity : 0,
                              borderRadius: 1,
                              pointerEvents: 'none',
                              transition: 'opacity 0.1s ease-out',
                              willChange: 'opacity',
                            }}
                          />
                        )}
                      </Box>

                      {/* Grad-CAM Controls */}
                      {currentImageUrls.gradcamUrl && (
                        <Box sx={{ px: 2, maxWidth: 400, mx: 'auto' }}>
                          {/* Toggle Button */}
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                            <Typography variant="body2" color="text.secondary">
                              Grad-CAM Overlay
                            </Typography>
                            <Button
                              size="small"
                              variant={gradcamEnabled ? "contained" : "outlined"}
                              color={gradcamEnabled ? "primary" : "inherit"}
                              startIcon={gradcamEnabled ? <VisibilityIcon /> : <VisibilityOffIcon />}
                              onClick={() => setGradcamEnabled(!gradcamEnabled)}
                              sx={{ minWidth: 100 }}
                            >
                              {gradcamEnabled ? 'ON' : 'OFF'}
                            </Button>
                          </Box>
                          
                          {/* Opacity Slider - always visible, disabled when OFF */}
                          <Typography variant="body2" color="text.secondary" gutterBottom>
                            Opacity: {(gradcamOpacity * 100).toFixed(0)}%
                          </Typography>
                          <Slider
                            value={gradcamOpacity}
                            onChange={(_, value) => setGradcamOpacity(value as number)}
                            min={0}
                            max={1}
                            step={0.01}
                            disabled={!imagesLoaded || !gradcamEnabled}
                            marks={[
                              { value: 0, label: '0%' },
                              { value: 0.5, label: '50%' },
                              { value: 1, label: '100%' },
                            ]}
                            valueLabelDisplay="auto"
                            valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
                            sx={{
                              '& .MuiSlider-thumb': {
                                transition: 'none',
                              },
                              '& .MuiSlider-track': {
                                transition: 'none',
                              },
                            }}
                          />
                        </Box>
                      )}
                    </>
                  ) : (
                    /* Placeholder for no results */
                    <Box sx={{ 
                      width: '100%',
                      maxWidth: 400,
                      mx: 'auto',
                      aspectRatio: '1',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: '2px dashed',
                      borderColor: 'divider',
                      borderRadius: 1,
                      bgcolor: 'background.default'
                    }}>
                      <Box sx={{ textAlign: 'center', p: 3 }}>
                        <ImageIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                        <Typography variant="body2" color="text.secondary">
                          No results yet
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Run inference or select from history
                        </Typography>
                      </Box>
                    </Box>
                  )}
                </Grid>
              </Grid>
            </Paper>
          </Grid>
        </Grid>

        {/* Bottom Section: Inference History Table */}
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              Inference History
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <TextField
                size="small"
                label="Search by date"
                placeholder="MM/DD/YYYY"
                value={historySearchDate}
                onChange={(e) => {
                  setHistorySearchDate(e.target.value);
                  setHistoryPage(0);
                }}
                sx={{ width: 200 }}
              />
              <Button
                size="small"
                startIcon={<RefreshIcon />}
                onClick={loadInferenceHistory}
                disabled={loadingHistory}
              >
                Refresh
              </Button>
            </Box>
          </Box>

          {loadingHistory ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress />
            </Box>
          ) : filteredHistory.length === 0 ? (
            <Box sx={{ textAlign: 'center', p: 3 }}>
              <Typography variant="body2" color="text.secondary">
                {historySearchDate ? 'No inference jobs found for this date' : 'No inference history yet'}
              </Typography>
            </Box>
          ) : (
            <>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Job ID</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Created At</TableCell>
                      <TableCell>Images</TableCell>
                      <TableCell>Duration</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {paginatedHistory.map((job) => (
                      <TableRow 
                        key={job.job_id}
                        hover
                        sx={{ 
                          bgcolor: jobId === job.job_id ? 'action.selected' : 'transparent',
                        }}
                      >
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                            {job.job_id}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={job.status}
                            color={getStatusColor(job.status)}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {formatDate(job.created_at)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {job.result?.num_images || '-'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {job.duration ? `${job.duration.toFixed(2)}s` : '-'}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <IconButton
                            size="small"
                            onClick={() => loadHistoryResults(job.job_id)}
                            disabled={job.status !== 'completed'}
                            color="primary"
                          >
                            <VisibilityIcon />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <TablePagination
                rowsPerPageOptions={[5, 10, 25, 50]}
                component="div"
                count={filteredHistory.length}
                rowsPerPage={historyRowsPerPage}
                page={historyPage}
                onPageChange={handleChangePage}
                onRowsPerPageChange={handleChangeRowsPerPage}
              />
            </>
          )}
        </Paper>
      </Container>
    </Layout>
    </ProtectedRoute>
  );
}
