'use client';
import { useState, useEffect } from 'react';
import {
  Snackbar,
  Alert,
  Button,
  Box,
  Typography,
} from '@mui/material';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { tokenSecondsRemaining } from '@/utils/jwt';

export default function TokenExpirationWarning() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [showWarning, setShowWarning] = useState(false);
  const [timeLeft, setTimeLeft] = useState<number>(0);

  useEffect(() => {
    if (!token) {
      setShowWarning(false);
      return;
    }

    const checkExpiration = () => {
      const seconds = tokenSecondsRemaining(token);
      setTimeLeft(seconds);
      setShowWarning(seconds > 0 && seconds <= 30);
    };

    checkExpiration();
    const interval = setInterval(checkExpiration, 5000);
    return () => clearInterval(interval);
  }, [token]);

  const handleExtendSession = () => {
    router.push('/login');
  };

  const handleLogoutNow = async () => {
    await logout();
    router.push('/login');
  };

  if (!showWarning || timeLeft <= 0) {
    return null;
  }

  return (
    <Snackbar
      open={showWarning}
      anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      sx={{ zIndex: 9999 }}
    >
      <Alert
        severity="warning"
        sx={{ 
          width: '100%',
          '& .MuiAlert-message': { width: '100%' }
        }}
      >
        <Box>
          <Typography variant="body2" fontWeight="bold" gutterBottom>
            Session Expiring Soon
          </Typography>
          <Typography variant="body2" gutterBottom>
            Your session will expire in {timeLeft} seconds. Please save your work.
          </Typography>
          <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
            <Button
              size="small"
              variant="contained"
              color="primary"
              onClick={handleExtendSession}
            >
              Re-login
            </Button>
            <Button
              size="small"
              variant="outlined"
              onClick={handleLogoutNow}
            >
              Logout Now
            </Button>
          </Box>
        </Box>
      </Alert>
    </Snackbar>
  );
}