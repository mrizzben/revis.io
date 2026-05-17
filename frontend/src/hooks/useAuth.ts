import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import * as authApi from '../api/endpoints/auth';
import apiClient from '../api/client';

export function useAuth() {
  const { accessToken, user, isAuthenticated, login: storeLogin, logout: storeLogout } = useAuthStore();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  // Session restore on mount
  useEffect(() => {
    async function restoreSession() {
      if (!accessToken) {
        setIsLoading(false);
        return;
      }

      try {
        const profile = await authApi.getMe();
        useAuthStore.getState().setUser(profile);
      } catch {
        // Token expired or invalid — try refresh
        try {
          const tokens = await authApi.refresh();
          useAuthStore.getState().setAccessToken(tokens.access_token);
          const profile = await authApi.getMe();
          useAuthStore.getState().setUser(profile);
        } catch {
          storeLogout();
        }
      } finally {
        setIsLoading(false);
      }
    }

    restoreSession();
  }, []); // Only on mount

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      setIsLoading(true);
      try {
        const tokens = await authApi.login(email, password);
        storeLogin(tokens.access_token, null);
        // Use the token directly for this first request
        const profile = await apiClient.get('/users/me', {
          headers: { Authorization: `Bearer ${tokens.access_token}` }
        });
        useAuthStore.getState().setUser(profile.data);
        navigate('/dashboard', { replace: true });
      } catch (err: unknown) {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(typeof msg === 'string' ? msg : 'Login failed');
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [navigate, storeLogin],
  );

  const register = useCallback(
    async (data: {
      email: string;
      password: string;
      name: string;
      role: 'architect' | 'client';
      invitation_token?: string;
    }) => {
      setError(null);
      setIsLoading(true);
      try {
        await authApi.register(data);
        if (data.role === 'architect') {
          // Auto-login after registration
          await login(data.email, data.password);
        } else {
          navigate('/login', { replace: true });
        }
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Registration failed');
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [navigate, login],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore errors on logout
    }
    storeLogout();
    navigate('/login', { replace: true });
  }, [navigate, storeLogout]);

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    register,
    logout,
    clearError: () => setError(null),
  };
}
