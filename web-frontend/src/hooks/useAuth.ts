/**
 * Authentication Hook for ContextForge
 * Handles JWT authentication with HTTP-only cookies and CSRF protection
 */

import { useState, useEffect, useCallback } from 'react';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8443';

export interface User {
  user_id: string;
  username: string;
  email?: string;
  roles: string[];
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface AuthState {
  user: User | null;
  csrfToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  setUser: (user: User | null) => void;
  setCSRFToken: (token: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  logout: () => void;
}

// Zustand store for auth state
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      csrfToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setCSRFToken: (csrfToken) => set({ csrfToken }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      logout: () => set({ user: null, csrfToken: null, isAuthenticated: false }),
    }),
    { 
      name: 'contextforge-auth',
      // Only persist user info, not tokens (tokens are in HTTP-only cookies)
      partialize: (state) => ({ user: state.user })
    }
  )
);

export const useAuth = () => {
  const { user, csrfToken, isAuthenticated, isLoading, error, setUser, setCSRFToken, setLoading, setError, logout: storeLogout } = useAuthStore();

  /**
   * Login with username and password
   */
  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include', // Important: include cookies
        body: JSON.stringify({ username, password })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(errorData.detail || 'Login failed');
      }

      const data: AuthTokens = await response.json();
      
      // CSRF token is set in cookie automatically by the server
      // Get it from response header if available
      const csrf = response.headers.get('X-CSRF-Token');
      if (csrf) {
        setCSRFToken(csrf);
      }
      
      // Fetch user info
      await fetchUserInfo();
      
      setLoading(false);
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      setLoading(false);
      return false;
    }
  }, [setLoading, setError, setCSRFToken]);

  /**
   * Logout and revoke tokens
   */
  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      storeLogout();
    }
  }, [storeLogout]);

  /**
   * Fetch current user info
   */
  const fetchUserInfo = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
        method: 'GET',
        credentials: 'include'
      });

      if (response.ok) {
        const userData: User = await response.json();
        setUser(userData);
      } else {
        setUser(null);
      }
    } catch (err) {
      console.error('Failed to fetch user info:', err);
      setUser(null);
    }
  }, [setUser]);

  /**
   * Make authenticated request with automatic token refresh
   */
  const makeAuthenticatedRequest = useCallback(async (
    url: string,
    options: RequestInit = {}
  ): Promise<Response> => {
    const headers: HeadersInit = {
      ...options.headers,
    };

    // Add CSRF token for state-changing requests
    if (csrfToken && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method || 'GET')) {
      headers['X-CSRF-Token'] = csrfToken;
    }

    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include' // Always include cookies
    });

    // Handle token expiration (401 Unauthorized)
    if (response.status === 401) {
      // Token might be expired, try to refresh
      // For now, just logout (refresh token logic can be added later)
      await logout();
      throw new Error('Session expired. Please login again.');
    }

    return response;
  }, [csrfToken, logout]);

  // Check authentication status on mount
  useEffect(() => {
    if (!user) {
      fetchUserInfo();
    }
  }, []);

  return {
    user,
    csrfToken,
    isAuthenticated,
    isLoading,
    error,
    login,
    logout,
    fetchUserInfo,
    makeAuthenticatedRequest
  };
};

