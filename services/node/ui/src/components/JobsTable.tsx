import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Typography,
} from '@mui/material';
import { useRouter } from 'next/navigation';

interface Job {
  job_id: string;
  job_type: string;
  status: string;
  result?: any;
  created_at: string;
}

interface JobsTableProps {
  jobs: Job[];
}

export default function JobsTable({ jobs }: JobsTableProps) {
  const router = useRouter();

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'success';
      case 'running':
        return 'info';
      case 'pending':
        return 'warning';
      case 'failed':
        return 'error';
      default:
        return 'default';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: '2-digit',
      day: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  };

  const getJobMessage = (job: Job) => {
    if (job.status === 'completed') {
      if (job.job_type === 'infer') {
        return 'Inference completed';
      } else if (job.job_type === 'federated_train') {
        return 'Federated training completed';
      }
      return 'Job completed';
    } else if (job.status === 'running') {
      return 'Job in progress...';
    } else if (job.status === 'pending') {
      return 'Waiting to start';
    } else if (job.status === 'failed') {
      return 'Job failed';
    }
    return '—';
  };

  const formatJobType = (jobType: string) => {
    switch (jobType) {
      case 'infer': return 'Inference';
      case 'federated_train': return 'Federated Training';
      default: return jobType;
    }
  };

  if (jobs.length === 0) {
    return (
      <Paper sx={{ borderRadius: 3, p: 4 }}>
        <Typography variant="body2" color="text.secondary" align="center">
          No recent jobs
        </Typography>
      </Paper>
    );
  }

  return (
    <TableContainer component={Paper} sx={{ borderRadius: 3 }}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 600 }}>Job</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Message</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Created</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {jobs.map((job) => (
            <TableRow
              key={job.job_id}
              hover
              sx={{ cursor: 'pointer' }}
              onClick={() => router.push('/jobs')}
            >
              <TableCell>{job.job_id}</TableCell>
              <TableCell>{formatJobType(job.job_type)}</TableCell>
              <TableCell>
                <Chip
                  label={job.status}
                  color={getStatusColor(job.status) as any}
                  size="small"
                />
              </TableCell>
              <TableCell>{getJobMessage(job)}</TableCell>
              <TableCell>{formatDate(job.created_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
