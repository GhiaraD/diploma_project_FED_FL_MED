/**
 * Decodes a JWT token and returns its payload.
 * Returns null if the token is invalid or cannot be decoded.
 */
export function decodeToken(token: string): Record<string, any> | null {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

/**
 * Returns true if the token is expired or cannot be decoded.
 */
export function isTokenExpired(token: string): boolean {
  const decoded = decodeToken(token);
  if (!decoded || !decoded.exp) return true;
  return decoded.exp < Math.floor(Date.now() / 1000);
}

/**
 * Returns seconds remaining until token expiration.
 * Returns 0 if already expired or invalid.
 */
export function tokenSecondsRemaining(token: string): number {
  const decoded = decodeToken(token);
  if (!decoded || !decoded.exp) return 0;
  return Math.max(0, decoded.exp - Math.floor(Date.now() / 1000));
}
