"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import {
  Box,
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Avatar,
  IconButton,
  InputAdornment,
} from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(email, password);

      // Read role from localStorage (set by login())
      const storedUser = localStorage.getItem('auth_user');
      const role = storedUser ? JSON.parse(storedUser).role : null;

      if (role === 'doctor') {
        router.push('/models');
      } else {
        router.push('/');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container component="main" maxWidth="xs">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Paper
          elevation={6}
          sx={{
            padding: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            width: '100%',
          }}
        >
          {/* Logo/Icon */}
          <Avatar sx={{ m: 1, bgcolor: 'primary.main', width: 56, height: 56 }}>
            <LockOutlinedIcon sx={{ fontSize: 32 }} />
          </Avatar>

          {/* Title */}
          <Typography component="h1" variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>
            Fed-Med-FL
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Federated Medical Learning Platform
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 3 }}>
            Sign in to your account
          </Typography>

          {/* Error Alert */}
          {error && (
            <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
              {error}
            </Alert>
          )}

          {/* Login Form */}
          <Box component="form" onSubmit={handleSubmit} sx={{ width: '100%' }}>
            <TextField
              margin="normal"
              required
              fullWidth
              id="email"
              label="Email Address"
              name="email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
              placeholder="admin@node1.fed-med-fl.com"
            />
            <TextField
              margin="normal"
              required
              fullWidth
              name="password"
              label="Password"
              type={showPassword ? 'text' : 'password'}
              id="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              slotProps={{
                input: {
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPassword((prev) => !prev)}
                        edge="end"
                        tabIndex={-1}
                      >
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                },
              }}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              sx={{ mt: 3, mb: 2, py: 1.5 }}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <CircularProgress size={20} sx={{ mr: 1 }} color="inherit" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </Button>

            {/* Info Text */}
            <Typography variant="caption" color="text.secondary" align="center" display="block" sx={{ mt: 2 }}>
              Contact your administrator for account access
            </Typography>
          </Box>

          {/* Footer */}
          <Box sx={{ mt: 3, pt: 3, borderTop: 1, borderColor: 'divider', width: '100%' }}>
            <Typography variant="caption" color="text.secondary" align="center" display="block">
              🔒 Secure authentication with JWT
            </Typography>
            <Typography variant="caption" color="text.secondary" align="center" display="block" sx={{ mt: 0.5 }}>
              Role-based access control enabled
            </Typography>
          </Box>
        </Paper>
      </Box>
    </Container>
  );
}
