'use client';
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';

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

  // Check if token is expired
  const isTokenExpired = useCallback((token: string) => {
    const decoded = decodeToken(token);
    if (!decoded || !decoded.exp) {
      return true;
    }
    
    const currentTime = Math.floor(Date.now() / 1000);
    return decoded.exp < currentTime;
  }, []);

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
    if (!token) {
      return false;
    }
    
    if (isTokenExpired(token)) {
      // Don't call forceLogout here to avoid infinite loops
      // Just return false and let the caller handle it
      return false;
    }
    
    return true;
  }, [token, isTokenExpired]);

  // Set up periodic token expiration check
  useEffect(() => {
    if (!token) {
      return;
    }

    // Check immediately
    if (isTokenExpired(token)) {
      forceLogout();
      return;
    }

    // Set up interval to check every 30 seconds
    const interval = setInterval(() => {
      if (token && isTokenExpired(token)) {
        forceLogout();
      }
    }, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, [token, isTokenExpired, forceLogout]);

  // Check for existing token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token');
    const storedUser = localStorage.getItem('auth_user');
    
    if (storedToken && storedUser) {
      // Check if stored token is expired
      if (isTokenExpired(storedToken)) {
        console.log('Stored token is expired, clearing...');
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
      } else {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      }
    }
    
    setIsLoading(false);
  }, [isTokenExpired]);

  const login = async (email: string, password: string) => {
    try {
      // Clear any existing token before login
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      localStorage.removeItem('auth_login_time');
      setToken(null);
      setUser(null);
      
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await fetch(`${apiBase}/api/auth/login`, {
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
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';
      
      if (token) {
        await fetch(`${apiBase}/api/auth/logout`, {
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
