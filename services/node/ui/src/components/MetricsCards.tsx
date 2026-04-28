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

  const metricsList = [
    { label: 'F1', value: metrics.f1 },
    { label: 'AUC', value: metrics.auc },
    { label: 'Sensitivity', value: metrics.sensitivity },
    { label: 'Specificity', value: metrics.specificity },
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
              {metric.value !== undefined ? metric.value.toFixed(2) : '—'}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}
