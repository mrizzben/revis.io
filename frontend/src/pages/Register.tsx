import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import * as authApi from '../api/endpoints/auth';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import apiClient from '../api/client';

const OAUTH_AUTHORIZE_URL = `${
  import.meta.env.VITE_API_URL || ''
}/api/auth/google/authorize`;

export default function Register() {
  const navigate = useNavigate();
  const { login: storeLogin } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState<'architect' | 'client'>('architect');
  const [invitationToken, setInvitationToken] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleGoogleSignUp = () => {
    window.location.href = OAUTH_AUTHORIZE_URL;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await authApi.register({
        email,
        password,
        name,
        role,
        invitation_token: role === 'client' ? invitationToken || undefined : undefined,
      });

      if (role === 'architect') {
        try {
          const tokens = await authApi.login(email, password);
          const user = await apiClient.get('/users/me', {
            headers: { Authorization: `Bearer ${tokens.access_token}` },
          });
          storeLogin(tokens.access_token, user.data);
          navigate('/dashboard', { replace: true });
        } catch {
          navigate('/login', { replace: true });
        }
      } else {
        navigate('/login', { replace: true });
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (detail && typeof detail === 'object' && Array.isArray(detail)) {
        setError(detail.map((d) => (d?.msg ? d.msg : 'Invalid input')).join('; '));
      } else if ((err as { response?: unknown })?.response) {
        setError('Registration failed');
      } else {
        setError('Cannot reach the server. Is the backend running?');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-secondary px-4">
      <div className="max-w-sm w-full">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <svg
              className="w-8 h-8 text-primary-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Revis.io</h1>
          </div>
          <p className="text-sm text-gray-500">Create your account</p>
        </div>

        <div className="border border-border bg-white p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-sm text-red-700">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">I am a...</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setRole('architect')}
                  className={`flex-1 py-2 px-3 text-sm font-medium border ${
                    role === 'architect'
                      ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'bg-white border-border text-gray-700'
                  }`}
                >
                  Architect
                </button>
                <button
                  type="button"
                  onClick={() => setRole('client')}
                  className={`flex-1 py-2 px-3 text-sm font-medium border ${
                    role === 'client'
                      ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'bg-white border-border text-gray-700'
                  }`}
                >
                  Client
                </button>
              </div>
            </div>

            <Input
              label="Full Name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="John Doe"
              required
            />

            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters"
              required
              minLength={8}
            />

            {role === 'client' && (
              <Input
                label="Invitation Token"
                type="text"
                value={invitationToken}
                onChange={(e) => setInvitationToken(e.target.value)}
                placeholder="Paste your invitation token"
                required
              />
            )}

            <Button type="submit" isLoading={isLoading} className="w-full">
              Create Account
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3">
            <div className="flex-1 border-t border-border" />
            <span className="text-xs text-gray-400">or</span>
            <div className="flex-1 border-t border-border" />
          </div>

          <button
            type="button"
            onClick={handleGoogleSignUp}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-border hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-1 transition-colors duration-150"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0012 23z" />
              <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 010-4.2V7.06H2.18a11 11 0 000 9.88l3.66-2.84z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            Sign up with Google
          </button>

          <div className="mt-6 text-center text-sm">
            <p>
              Already have an account?{' '}
              <Link to="/login" className="text-primary-600 hover:text-primary-500 font-medium">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
