'use client';
import { useState, useEffect } from 'react';
import {
  Snackbar,
  Alert,
  Button,
  Box,
  Typography,
} from '@mui/material';
import { useAuth } from '@/contexts/AuthContext';

export default function TokenExpirationWarning() {
  const { token, logout } = useAuth();
  const [showWarning, setShowWarning] = useState(false);
  const [timeLeft, setTimeLeft] = useState<number>(0);

  // Decode JWT token to get expiration time
  const decodeToken = (token: string) => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join(''));
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Error decoding token:', error);
      return null;
    }
  };

  useEffect(() => {
    if (!token) {
      setShowWarning(false);
      return;
    }

    const checkExpiration = () => {
      const decoded = decodeToken(token);
      if (!decoded || !decoded.exp) {
        return;
      }

      const currentTime = Math.floor(Date.now() / 1000);
      const expirationTime = decoded.exp;
      const timeUntilExpiration = expirationTime - currentTime;

      setTimeLeft(timeUntilExpiration);

      // Show warning if less than 30 seconds left (for 3-minute tokens)
      if (timeUntilExpiration > 0 && timeUntilExpiration <= 30) {
        setShowWarning(true);
      } else {
        setShowWarning(false);
      }
    };

    // Check immediately
    checkExpiration();

    // Set up interval to check every 5 seconds
    const interval = setInterval(checkExpiration, 5000);

    return () => clearInterval(interval);
  }, [token]);

  const handleExtendSession = () => {
    // For now, just redirect to login page
    // In a real app, you might want to refresh the token
    window.location.href = '/login';
  };

  const handleLogoutNow = async () => {
    await logout();
    window.location.href = '/login';
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