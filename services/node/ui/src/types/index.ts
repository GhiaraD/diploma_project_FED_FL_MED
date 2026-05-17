// Shared types used across multiple pages

export interface Job {
  job_id: string;
  job_type: string;
  status: string;
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration: number | null;
}

export interface ModelMetrics {
  accuracy?: number;
  f1?: number;
  auc?: number;
  sensitivity?: number;
  specificity?: number;
}

export interface Model {
  model_id: string;
  model_name: string;
  version: string;
  type: string;
  labels: string[];
  session_id: string | null;
  metrics: ModelMetrics | null;
  created_at: string;
}
