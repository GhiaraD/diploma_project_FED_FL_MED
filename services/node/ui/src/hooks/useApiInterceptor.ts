'use client';
import { useEffect, useRef } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';

export const useApiInterceptor = () => {
  const { token, logout, checkTokenExpiration, forceLogout } = useAuth();
  const router = useRouter();

  // Keep latest values accessible inside the patched fetch without re-patching
  const stateRef = useRef({ token, logout, checkTokenExpiration, forceLogout, router });
  useEffect(() => {
    stateRef.current = { token, logout, checkTokenExpiration, forceLogout, router };
  });

  useEffect(() => {
    // Guard: patch only once — the same patchedFetch stays for the lifetime of the app
    if ((window.fetch as any).__intercepted) {
      return;
    }

    const originalFetch = window.fetch;

    const patchedFetch = async (...args: Parameters<typeof fetch>) => {
      const { token: currentToken, checkTokenExpiration: checkExp, forceLogout: doForceLogout, logout: doLogout, router: currentRouter } = stateRef.current;

      // Check token expiration before making the request
      if (currentToken && !checkExp()) {
        doForceLogout();
        throw new Error('Token expired');
      }

      const response = await originalFetch(...args);

      // On 401, log out — but not for the login endpoint itself
      if (response.status === 401) {
        const url = typeof args[0] === 'string' ? args[0] : (args[0] as Request).url;
        if (!url.includes('/api/auth/login')) {
          await doLogout();
          setTimeout(() => currentRouter.push('/login'), 0);
        }
      }

      return response;
    };

    (patchedFetch as any).__intercepted = true;
    window.fetch = patchedFetch;

    // No cleanup: the patch is intentionally permanent for the app lifetime.
    // Removing it on unmount would break fetch for any component that outlives Layout.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
};