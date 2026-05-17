'use client';
import { useState, useEffect, useRef, useMemo, useCallback, memo } from 'react';
import { FixedSizeList } from 'react-window';
import {
  Container,
  Typography,
  Paper,
  Button,
  Box,
  CircularProgress,
  Alert,
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
import { API_BASE } from '@/config/api';

const apiBase = API_BASE;

// ─── Grad-CAM split components ───────────────────────────────────────────────
// State lives in the parent (InferencePage) via a shared ref object.
// GradcamControls renders the toggle + slider in the left column.
// GradcamImage renders only the image + overlay in the right column.
// Slider drags update the overlay DOM directly — zero re-render on the page.

interface GradcamRef {
  overlayEl: HTMLImageElement | null;
  opacity: number;
  enabled: boolean;
}

interface GradcamImageProps {
  imageUrl: string | null;
  gradcamUrl: string | null;
  imagesLoaded: boolean;
  sharedRef: React.MutableRefObject<GradcamRef>;
}

const GradcamImage = memo(function GradcamImage({
  imageUrl, gradcamUrl, imagesLoaded, sharedRef,
}: GradcamImageProps) {
  const overlayRef = useRef<HTMLImageElement>(null);

  // Keep sharedRef.overlayEl in sync
  useEffect(() => {
    sharedRef.current.overlayEl = overlayRef.current;
  });

  // Apply opacity when images finish loading
  useEffect(() => {
    if (overlayRef.current) {
      overlayRef.current.style.opacity =
        imagesLoaded && sharedRef.current.enabled
          ? String(sharedRef.current.opacity)
          : '0';
    }
  }, [imagesLoaded, sharedRef]);

  return (
    <Box sx={{
      position: 'relative',
      width: '100%',
      height: 400,
      borderRadius: 1,
      border: '1px solid',
      borderColor: 'divider',
      overflow: 'hidden',
      bgcolor: 'background.default',
    }}>
      {!imagesLoaded && (
        <Box sx={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)', zIndex: 10,
        }}>
          <CircularProgress />
        </Box>
      )}
      <Box
        component="img"
        src={imageUrl || ''}
        alt="Original"
        sx={{
          width: '100%', height: '100%',
          objectFit: 'contain', display: 'block',
          opacity: imagesLoaded ? 1 : 0.3,
          transition: 'opacity 0.3s ease-in-out',
        }}
      />
      {gradcamUrl && (
        <Box
          ref={overlayRef}
          component="img"
          src={gradcamUrl}
          alt="Grad-CAM"
          sx={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%',
            objectFit: 'contain',
            opacity: 0,
            pointerEvents: 'none',
            willChange: 'opacity',
            transform: 'translateZ(0)',
          }}
        />
      )}
    </Box>
  );
});

interface GradcamControlsProps {
  gradcamUrl: string | null;
  imagesLoaded: boolean;
  sharedRef: React.MutableRefObject<GradcamRef>;
}

const GradcamControls = memo(function GradcamControls({
  gradcamUrl, imagesLoaded, sharedRef,
}: GradcamControlsProps) {
  const [opacityLabel, setOpacityLabel] = useState(sharedRef.current.opacity);
  const [enabled, setEnabled] = useState(sharedRef.current.enabled);

  const handleChange = useCallback((_: any, value: number | number[]) => {
    const v = value as number;
    sharedRef.current.opacity = v;
    if (sharedRef.current.overlayEl && sharedRef.current.enabled) {
      sharedRef.current.overlayEl.style.opacity = String(v);
    }
  }, [sharedRef]);

  const handleChangeCommitted = useCallback((_: any, value: number | number[]) => {
    setOpacityLabel(value as number);
  }, []);

  const handleToggle = useCallback(() => {
    const next = !sharedRef.current.enabled;
    sharedRef.current.enabled = next;
    setEnabled(next);
    if (sharedRef.current.overlayEl) {
      sharedRef.current.overlayEl.style.opacity = next
        ? String(sharedRef.current.opacity)
        : '0';
    }
  }, [sharedRef]);

  if (!gradcamUrl) {
    return (
      <Card>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Grad-CAM Overlay
          </Typography>
          <Typography variant="caption" color="text.secondary">
            No Grad-CAM available
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Grad-CAM Overlay
          </Typography>
          <Button
            size="small"
            variant={enabled ? 'contained' : 'outlined'}
            color={enabled ? 'primary' : 'inherit'}
            startIcon={enabled ? <VisibilityIcon /> : <VisibilityOffIcon />}
            onClick={handleToggle}
            sx={{ minWidth: 80 }}
          >
            {enabled ? 'ON' : 'OFF'}
          </Button>
        </Box>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Opacity: {(opacityLabel * 100).toFixed(0)}%
        </Typography>
        <Slider
          defaultValue={sharedRef.current.opacity}
          onChange={handleChange}
          onChangeCommitted={handleChangeCommitted}
          min={0} max={1} step={0.01}
          disabled={!imagesLoaded || !enabled}
          marks={[
            { value: 0, label: '0%' },
            { value: 0.5, label: '50%' },
            { value: 1, label: '100%' },
          ]}
          valueLabelDisplay="auto"
          valueLabelFormat={(v) => `${(v * 100).toFixed(0)}%`}
          sx={{
            '& .MuiSlider-thumb': { transition: 'none' },
            '& .MuiSlider-track': { transition: 'none' },
          }}
        />
      </CardContent>
    </Card>
  );
});
// ─────────────────────────────────────────────────────────────────────────────

// ─── FileItem ─────────────────────────────────────────────────────────────────
// Memoized so only the clicked item re-renders on selection change.
interface FileItemProps {
  file: { path: string; name: string; size: number };
  selected: boolean;
  onToggle: (path: string) => void;
}

const FileItem = memo(function FileItem({ file, selected, onToggle }: FileItemProps) {
  // Stable click handler — recreated only if file.path or onToggle changes
  const handleClick = useCallback(() => onToggle(file.path), [onToggle, file.path]);

  return (
    <ListItem disablePadding>
      <ListItemButton
        onClick={handleClick}
        disableRipple
        disableTouchRipple
      >
        <Checkbox
          edge="start"
          checked={selected}
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
  );
// Custom comparator: only re-render when selection changes
}, (prev, next) => prev.selected === next.selected && prev.file.path === next.file.path && prev.onToggle === next.onToggle);
// ─────────────────────────────────────────────────────────────────────────────

export default function InferencePage() {
  const { token } = useAuth();
  const [currentDir, setCurrentDir] = useState('/storage/datasets');
  const [files, setFiles] = useState<any[]>([]);
  const [subdirs, setSubdirs] = useState<any[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [filesTotalTruncated, setFilesTotalTruncated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  
  // History state
  const [inferenceHistory, setInferenceHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyPage, setHistoryPage] = useState(0);
  const [historyRowsPerPage, setHistoryRowsPerPage] = useState(10);
  const [historySearchDate, setHistorySearchDate] = useState('');
  
  // Viewer state
  const [selectedResultIndex, setSelectedResultIndex] = useState<number>(0);

  // Shared ref between GradcamControls (left) and GradcamImage (right)
  const gradcamSharedRef = useRef<GradcamRef>({ overlayEl: null, opacity: 0.4, enabled: true });

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
      setFilesTotalTruncated(data.truncated || false);
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
    return () => {
      // Clean up any active polling interval on unmount
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [token]);

  // Load inference history - silent version (no loading spinner) for background refreshes
  const loadInferenceHistorySilent = async () => {
    try {
      const response = await fetch(`${apiBase}/api/jobs/list?job_type=infer&limit=100`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) return;
      const data = await response.json();
      setInferenceHistory(data.jobs || []);
    } catch (err) {
      // silent fail
    }
  };

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
  const toggleFileSelection = useCallback((path: string) => {
    setSelectedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  // Run inference
  const handleInference = async () => {
    if (selectedPaths.size === 0) {
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
          image_paths: Array.from(selectedPaths),
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
      loadInferenceHistorySilent();
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Inference failed');
      setLoading(false);
    }
  };

  // Poll for inference results
  const pollResults = (activeJobId: string) => {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;

    // Clear any existing poll before starting a new one
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        attempts++;

        const response = await fetch(`${apiBase}/api/infer/results/${activeJobId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
        const data = await response.json();

        if (data.status === 'completed') {
          clearInterval(pollIntervalRef.current!);
          pollIntervalRef.current = null;
          setResults(data.results || []);
          setSelectedResultIndex(0);
          setLoading(false);
          loadInferenceHistorySilent();
        } else if (data.status === 'failed') {
          clearInterval(pollIntervalRef.current!);
          pollIntervalRef.current = null;
          setError('Inference job failed');
          setLoading(false);
        } else if (attempts >= maxAttempts) {
          clearInterval(pollIntervalRef.current!);
          pollIntervalRef.current = null;
          setError('Inference timeout');
          setLoading(false);
        }
      } catch (err) {
        clearInterval(pollIntervalRef.current!);
        pollIntervalRef.current = null;
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
        <Box sx={{ display: 'grid', gridTemplateColumns: '3fr 6fr', gap: 3, mb: 3 }}>
          {/* Browse Images */}
          <Box>
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
                    Images ({files.length}{filesTotalTruncated ? ', showing first 200' : ''})
                  </Typography>
                  {filesTotalTruncated && (
                    <Alert severity="info" sx={{ mb: 1, py: 0 }}>
                      Directory has more than 200 images.
                    </Alert>
                  )}
                  {files.length === 0 ? (
                    <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                      No images found
                    </Typography>
                  ) : (
                    <FixedSizeList
                      height={300}
                      itemCount={files.length}
                      itemSize={48}
                      width="100%"
                      style={{ overflowX: 'hidden' }}
                    >
                      {({ index, style }) => (
                        <div style={style}>
                          <FileItem
                            file={files[index]}
                            selected={selectedPaths.has(files[index].path)}
                            onToggle={toggleFileSelection}
                          />
                        </div>
                      )}
                    </FixedSizeList>
                  )}
                </>
              )}

              <Box sx={{ mt: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Selected: {selectedPaths.size} image(s)
                </Typography>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<PsychologyIcon />}
                  onClick={handleInference}
                  disabled={selectedPaths.size === 0 || loading}
                  fullWidth
                >
                  {loading ? <CircularProgress size={24} /> : 'Run Inference'}
                </Button>
              </Box>
            </Paper>
          </Box>

          {/* Results Viewer */}
          <Box>
            <Paper sx={{ p: 3, height: '100%' }}>
              <Typography variant="h6" gutterBottom>
                Results
              </Typography>

              {/* Results Display - Always show both columns */}
              <Box sx={{ display: 'grid', gridTemplateColumns: '3fr 6fr', gap: 2 }}>
                {/* Left Column: Prediction & Probabilities */}
                <Box>
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
                      <Card sx={{ mb: 2 }}>
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

                      {/* Grad-CAM Controls — in left column */}
                      <GradcamControls
                        gradcamUrl={currentImageUrls.gradcamUrl}
                        imagesLoaded={imagesLoaded}
                        sharedRef={gradcamSharedRef}
                      />
                    </>
                  ) : (
                    <>
                      {/* Empty Prediction Card - same structure as filled */}
                      <Card sx={{ mb: 2 }}>
                        <CardContent>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                            <Typography variant="subtitle2" color="text.secondary">
                              Prediction
                            </Typography>
                            <Chip label="—" size="small" />
                          </Box>
                          <Typography variant="h4" gutterBottom color="text.disabled">
                            —
                          </Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                            No image selected
                          </Typography>
                        </CardContent>
                      </Card>

                      {/* Empty Probabilities Card - same structure as filled */}
                      <Card sx={{ mb: 2 }}>
                        <CardContent>
                          <Typography variant="subtitle2" gutterBottom>
                            Class Probabilities
                          </Typography>
                          <Box sx={{ mt: 1 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                              <Typography variant="body2" color="text.secondary">NORMAL</Typography>
                              <Typography variant="body2" color="text.disabled">—</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                              <Typography variant="body2" color="text.secondary">PNEUMONIA</Typography>
                              <Typography variant="body2" color="text.disabled">—</Typography>
                            </Box>
                          </Box>
                        </CardContent>
                      </Card>

                      {/* Grad-CAM Controls placeholder — disabled when no results */}
                      <GradcamControls
                        gradcamUrl={null}
                        imagesLoaded={false}
                        sharedRef={gradcamSharedRef}
                      />
                    </>
                  )}
                </Box>

                {/* Right Column: Image & Opacity */}
                <Box>
                  {/* Navigation - centered over the image column */}
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 1 }}>
                    <IconButton
                      onClick={() => setSelectedResultIndex(Math.max(0, selectedResultIndex - 1))}
                      disabled={results.length === 0 || selectedResultIndex === 0 || results.length <= 1}
                    >
                      <NavigateBeforeIcon />
                    </IconButton>
                    <Typography variant="body2" sx={{ mx: 2 }}>
                      {results.length > 0 ? `${selectedResultIndex + 1} / ${results.length}` : '0 / 0'}
                    </Typography>
                    <IconButton
                      onClick={() => setSelectedResultIndex(Math.min(results.length - 1, selectedResultIndex + 1))}
                      disabled={results.length === 0 || selectedResultIndex === results.length - 1 || results.length <= 1}
                    >
                      <NavigateNextIcon />
                    </IconButton>
                  </Box>
                  {results.length > 0 && results[selectedResultIndex] ? (
                    <GradcamImage
                      imageUrl={currentImageUrls.imageUrl}
                      gradcamUrl={currentImageUrls.gradcamUrl}
                      imagesLoaded={imagesLoaded}
                      sharedRef={gradcamSharedRef}
                    />
                  ) : (
                    /* Placeholder */
                    <Box sx={{
                      position: 'relative',
                      width: '100%',
                      height: 400,
                      borderRadius: 1,
                      border: '2px dashed',
                      borderColor: 'divider',
                      overflow: 'hidden',
                      bgcolor: 'background.default',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <Box sx={{ textAlign: 'center', p: 3 }}>
                        <ImageIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                        <Typography variant="body2" color="text.secondary">No results yet</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Run inference or select from history
                        </Typography>
                      </Box>
                    </Box>
                  )}
                </Box>
              </Box>
            </Paper>
          </Box>
        </Box>

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
