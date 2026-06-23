'use client';
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { isTokenExpired } from '@/utils/jwt';
import { API_BASE } from '@/config/api';

interface User {
  id: string;
  email: string;
  role: string;
  node_id: string;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
  checkTokenExpiration: () => boolean;
  forceLogout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  // Force logout when token expires
  const forceLogout = useCallback(() => {
    console.log('Token expired, forcing logout...');
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    setToken(null);
    setUser(null);
    // Use setTimeout to avoid potential issues with router.push in callbacks
    setTimeout(() => {
      router.push('/login');
    }, 0);
  }, [router]);

  // Check token expiration
  const checkTokenExpiration = useCallback(() => {
    if (!token) return false;
    return !isTokenExpired(token);
  }, [token]);

  // Set up periodic token expiration check
  useEffect(() => {
    if (!token) return;

    if (isTokenExpired(token)) {
      forceLogout();
      return;
    }

    const interval = setInterval(() => {
      if (token && isTokenExpired(token)) {
        forceLogout();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [token, forceLogout]);

  // Check for existing token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token');
    const storedUser = localStorage.getItem('auth_user');

    if (storedToken && storedUser) {
      if (isTokenExpired(storedToken)) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
      } else {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      }
    }

    setIsLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    try {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      localStorage.removeItem('auth_login_time');
      setToken(null);
      setUser(null);

      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
      }

      const data = await response.json();
      
      // Store token and user info with fresh timestamp
      const loginTime = Date.now();
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('auth_user', JSON.stringify(data.user));
      localStorage.setItem('auth_login_time', loginTime.toString());
      
      setToken(data.access_token);
      setUser(data.user);
      
      console.log(`✅ Login successful - Token duration reset. Expires in ${data.expires_in} seconds`);
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  };

  const logout = async () => {
    try {
      if (token) {
        await fetch(`${API_BASE}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local storage and state
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      localStorage.removeItem('auth_login_time');
      setToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        isAuthenticated: !!token && !!user,
        isLoading,
        checkTokenExpiration,
        forceLogout, // Expose forceLogout for external use
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
