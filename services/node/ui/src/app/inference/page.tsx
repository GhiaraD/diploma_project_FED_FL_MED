'use client';
import { useState } from 'react';
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
  CardMedia,
  Chip,
} from '@mui/material';
import { Upload as UploadIcon, Psychology as PsychologyIcon } from '@mui/icons-material';
import Layout from '@/components/Layout';

export default function InferencePage() {
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);

  const handleInference = async () => {
    if (!selectedFiles || selectedFiles.length === 0) {
      setError('Please select at least one image');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Note: This is a simplified version
      // In production, you'd upload images first, then run inference
      setError('Inference feature requires image upload implementation');
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Inference failed');
    } finally {
      setLoading(false);
    }
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
          <Grid item={true} xs={12} md={8}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Upload Images
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph={true}>
                Upload chest X-ray images for pneumonia detection with Grad-CAM visualization.
              </Typography>

              <Button
                variant="outlined"
                component="label"
                startIcon={<UploadIcon />}
                fullWidth
                sx={{ mb: 2 }}
              >
                {selectedFiles ? `${selectedFiles.length} file(s) selected` : 'Choose Images'}
                <input
                  type="file"
                  hidden
                  multiple
                  accept="image/*"
                  onChange={(e) => setSelectedFiles(e.target.files)}
                />
              </Button>

              <Button
                variant="contained"
                size="large"
                startIcon={<PsychologyIcon />}
                onClick={handleInference}
                disabled={!selectedFiles || loading}
                fullWidth
              >
                {loading ? <CircularProgress size={24} /> : 'Run Inference'}
              </Button>
            </Paper>

            {/* Results */}
            {results.length > 0 && (
              <Paper sx={{ p: 3, mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Results
                </Typography>
                <Grid container spacing={2}>
                  {results.map((result, idx) => (
                    <Grid item={true} xs={12} sm={6} md={4} key={idx}>
                      <Card>
                        <CardMedia
                          component="img"
                          height="200"
                          image={result.image_url}
                          alt={`Result ${idx + 1}`}
                        />
                        <CardContent>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                            <Typography variant="body2">
                              Prediction:
                            </Typography>
                            <Chip
                              label={result.predicted_class === 0 ? 'NORMAL' : 'PNEUMONIA'}
                              color={result.predicted_class === 0 ? 'success' : 'error'}
                              size="small"
                            />
                          </Box>
                          <Typography variant="body2">
                            Confidence: {(result.confidence * 100).toFixed(2)}%
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </Paper>
            )}
          </Grid>

          <Grid item={true} xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  About Inference
                </Typography>
                <Typography variant="body2" paragraph>
                  The inference service will:
                </Typography>
                <Typography variant="body2" component="div">
                  • Use the deployed model from the registry
                </Typography>
                <Typography variant="body2" component="div">
                  • Classify images as NORMAL or PNEUMONIA
                </Typography>
                <Typography variant="body2" component="div">
                  • Generate Grad-CAM heatmaps
                </Typography>
                <Typography variant="body2" component="div">
                  • Show confidence scores
                </Typography>
              </CardContent>
            </Card>

            <Card sx={{ mt: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Grad-CAM
                </Typography>
                <Typography variant="body2">
                  Gradient-weighted Class Activation Mapping (Grad-CAM) provides visual explanations
                  for the model's predictions by highlighting the regions of the image that were most
                  important for the classification decision.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Container>
    </Layout>
  );
}
