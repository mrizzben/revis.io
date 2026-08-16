import { useState } from 'react';
import { Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import * as authApi from '../api/endpoints/auth';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import apiClient from '../api/client';

const OAUTH_AUTHORIZE_URL = `${import.meta.env.VITE_API_URL || ''}/api/auth/google/authorize`;

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { login: storeLogin } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const verifyToken = searchParams.get('verify');
  const resetToken = searchParams.get('reset');
  const oauthError = searchParams.get('error');

  const handleGoogleLogin = () => {
    window.location.href = OAUTH_AUTHORIZE_URL;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const tokens = await authApi.login(email, password);
      const user = await apiClient.get('/users/me', {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      });
      storeLogin(tokens.access_token, user.data);

      const from = (location.state as { from?: { pathname: string } })?.from?.pathname;
      navigate(from || '/dashboard', { replace: true });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyEmail = async () => {
    if (!verifyToken) return;
    try {
      await authApi.verifyEmail(verifyToken);
      setError('');
      alert('Email verified! You can now log in.');
    } catch {
      setError('Invalid or expired verification token');
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
          <p className="text-sm text-gray-500">Sign in to your account</p>
        </div>

        <div className="border border-border bg-white p-6">
          {verifyToken && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 text-sm text-blue-700">
              Click "Verify Email" below to activate your account.
              <button onClick={handleVerifyEmail} className="ml-2 underline font-medium">
                Verify Email
              </button>
            </div>
          )}

          {oauthError && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 text-sm text-amber-700">
              Google sign-in failed. Please try again or use your email and password.
            </div>
          )}

          {resetToken && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 text-sm text-blue-700">
              Reset token detected. Use the forgot password flow to set a new password.
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-sm text-red-700">
                {error}
              </div>
            )}

            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              required
              autoComplete="current-password"
            />

            <Button type="submit" isLoading={isLoading} className="w-full">
              Sign in
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3">
            <div className="flex-1 border-t border-border" />
            <span className="text-xs text-gray-400">or</span>
            <div className="flex-1 border-t border-border" />
          </div>

          <button
            type="button"
            onClick={handleGoogleLogin}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-border hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-1 transition-colors duration-150"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0012 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.1a6.6 6.6 0 010-4.2V7.06H2.18a11 11 0 000 9.88l3.66-2.84z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            Continue with Google
          </button>

          <div className="mt-6 text-center text-sm space-y-2">
            <p>
              <Link to="/register" className="text-primary-600 hover:text-primary-500 font-medium">
                Register as an architect
              </Link>
            </p>
            <p>
              <a href="#" className="text-gray-500 hover:text-gray-700">
                Forgot your password?
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
