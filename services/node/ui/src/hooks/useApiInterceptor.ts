'use client';
import { useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';

export const useApiInterceptor = () => {
  const { token, logout, checkTokenExpiration, forceLogout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Intercept fetch requests to check for 401 responses
    const originalFetch = window.fetch;
    
    window.fetch = async (...args) => {
      // Check token expiration before making request
      if (token && !checkTokenExpiration()) {
        // Token expired, force logout
        console.log('Token expired before request, forcing logout...');
        forceLogout();
        
        // Return a rejected promise with a proper Response object
        return Promise.reject(new Response(
          JSON.stringify({ detail: 'Token expired' }), 
          { 
            status: 401, 
            statusText: 'Unauthorized',
            headers: { 'Content-Type': 'application/json' }
          }
        ));
      }

      try {
        const response = await originalFetch(...args);
        
        // Check if response is 401 (Unauthorized)
        if (response.status === 401) {
          console.log('Received 401 response, token may be expired');
          
          // Check if this is an auth-related request
          const url = typeof args[0] === 'string' ? args[0] : args[0].url;
          if (url.includes('/api/') && !url.includes('/api/auth/login')) {
            // Force logout and redirect to login
            await logout();
            setTimeout(() => {
              router.push('/login');
            }, 0);
          }
        }
        
        return response;
      } catch (error) {
        // Log the error but let it propagate normally
        console.error('Fetch error:', error);
        throw error;
      }
    };

    // Cleanup: restore original fetch on unmount
    return () => {
      window.fetch = originalFetch;
    };
  }, [token, logout, router, checkTokenExpiration, forceLogout]);
};