import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getClientAccessInfo, authenticateClientAccess } from '../api/endpoints/clientAccess';
import useAuthStore from '../stores/authStore';
import apiClient from '../api/client';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import type { ClientAccessInfo } from '../types';

export default function ClientAccessAccept() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { login: storeLogin } = useAuthStore();

  const [info, setInfo] = useState<ClientAccessInfo | null>(null);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    async function loadInfo() {
      if (!token) {
        setError('No access token provided');
        setIsLoading(false);
        return;
      }
      try {
        const data = await getClientAccessInfo(token);
        setInfo(data);
      } catch {
        setError('This link is invalid or has expired');
      } finally {
        setIsLoading(false);
      }
    }
    loadInfo();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError('');
    setIsSubmitting(true);

    try {
      const result = await authenticateClientAccess({ token, password });
      // Store the token and fetch user info (includes client_project_id)
      const user = await apiClient.get('/users/me', {
        headers: { Authorization: `Bearer ${result.access_token}` },
      });
      storeLogin(result.access_token, user.data);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Invalid password or link');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error && !info) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="card max-w-md w-full text-center">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Access Link Error</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <Link to="/login">
            <Button variant="secondary">Go to Login</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="card max-w-md w-full">
        <div className="text-center mb-6">
          <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>

          <h2 className="text-xl font-semibold text-gray-900 mb-2">Client Access</h2>
          {info && (
            <p className="text-gray-600">
              You have been invited to review <strong className="text-primary-600">{info.project_name}</strong>
            </p>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
          )}

          <Input
            label="Access Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter the password provided by the project owner"
            required
            autoComplete="off"
          />

          <div className="text-xs text-gray-500">
            No account needed. Enter the password shared by the project owner to view and comment on designs.
          </div>

          <Button type="submit" isLoading={isSubmitting} className="w-full">
            Access Project
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-gray-500">
          Already have an account?{' '}
          <Link to="/login" className="text-primary-600 hover:text-primary-500 font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}