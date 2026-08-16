import { useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import apiClient from '../api/client';
import Spinner from '../components/ui/Spinner';

export default function OAuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login: storeLogin } = useAuthStore();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const params = new URLSearchParams(location.hash.slice(1));
    const accessToken = params.get('access_token');
    const error = params.get('error');

    if (error || !accessToken) {
      navigate(`/login?error=${error || 'google_oauth_failed'}`, { replace: true });
      return;
    }

    const finalize = async () => {
      try {
        const user = await apiClient.get('/users/me', {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        storeLogin(accessToken, user.data);
        navigate('/dashboard', { replace: true });
      } catch {
        navigate('/login?error=google_oauth_failed', { replace: true });
      }
    };
    finalize();
  }, [location.hash, navigate, storeLogin]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-secondary px-4">
      <div className="text-center">
        <Spinner />
        <p className="mt-4 text-sm text-gray-500">Completing sign in with Google…</p>
      </div>
    </div>
  );
}
