import { Box, Card, CardContent, Typography } from '@mui/material';

interface Metrics {
  f1?: number;
  auc?: number;
  sensitivity?: number;
  specificity?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
}

interface MetricsCardsProps {
  metrics?: Metrics;
}

export default function MetricsCards({ metrics }: MetricsCardsProps) {
  if (!metrics) {
    return (
      <Card sx={{ borderRadius: 3, p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          No metrics available. Deploy a model to see metrics.
        </Typography>
      </Card>
    );
  }

  // Prioritize available metrics, fallback to common ones
  const metricsList = [
    { 
      label: 'Accuracy', 
      value: metrics.accuracy,
      format: (v: number) => `${(v * 100).toFixed(2)}%`
    },
    { 
      label: 'F1 Score', 
      value: metrics.f1,
      format: (v: number) => v.toFixed(4)
    },
    { 
      label: 'AUC', 
      value: metrics.auc,
      format: (v: number) => v.toFixed(4)
    },
    { 
      label: 'Precision', 
      value: metrics.precision,
      format: (v: number) => v.toFixed(4)
    },
  ];

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
        gap: 2,
      }}
    >
      {metricsList.map((metric) => (
        <Card key={metric.label} sx={{ borderRadius: 3 }}>
          <CardContent>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              {metric.label}
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {metric.value !== undefined ? metric.format(metric.value) : (
                <Typography component="span" variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
                  N/A
                </Typography>
              )}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}
