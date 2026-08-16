import { useState } from 'react';
import { Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import * as authApi from '../api/endpoints/auth';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import apiClient from '../api/client';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { login: storeLogin } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [showForgot, setShowForgot] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSent, setForgotSent] = useState(false);
  const [forgotLoading, setForgotLoading] = useState(false);
  const [verified, setVerified] = useState(false);

  const verifyToken = searchParams.get('verify');
  const resetToken = searchParams.get('reset');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const tokens = await authApi.login(email, password);
      storeLogin(tokens.access_token, null);
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
      setVerified(true);
    } catch {
      setError('Invalid or expired verification token');
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setForgotLoading(true);
    try {
      await authApi.forgotPassword({ email: forgotEmail });
      setForgotSent(true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Could not send reset email. Please try again.');
    } finally {
      setForgotLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-secondary px-4 py-10">
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

        <div className="card p-6">
          {verified && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 text-sm text-green-700">
              Email verified! You can now log in.
            </div>
          )}

          {verifyToken && !verified && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 text-sm text-blue-700">
              Click &ldquo;Verify Email&rdquo; below to activate your account.
              <button
                onClick={handleVerifyEmail}
                className="ml-2 underline font-medium cursor-pointer"
              >
                Verify Email
              </button>
            </div>
          )}

          {resetToken && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 text-sm text-blue-700">
              Check your email for a password reset link to set a new password.
            </div>
          )}

          {showForgot ? (
            <form onSubmit={handleForgotPassword} className="space-y-4">
              <h2 className="text-base font-semibold text-gray-900">Reset your password</h2>
              <p className="text-sm text-gray-500">
                Enter your account email and we&apos;ll send you a reset link.
              </p>
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 text-sm text-red-700">
                  {error}
                </div>
              )}
              {forgotSent ? (
                <div className="p-3 bg-green-50 border border-green-200 text-sm text-green-700">
                  If an account exists for <span className="font-medium">{forgotEmail}</span>, a
                  password reset link has been sent. Check your inbox.
                </div>
              ) : (
                <>
                  <Input
                    label="Email"
                    type="email"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    autoComplete="email"
                  />
                  <Button type="submit" isLoading={forgotLoading} className="w-full">
                    Send reset link
                  </Button>
                </>
              )}
              <button
                type="button"
                onClick={() => {
                  setShowForgot(false);
                  setError('');
                }}
                className="text-sm text-gray-500 hover:text-gray-700 cursor-pointer"
              >
                ← Back to sign in
              </button>
            </form>
          ) : (
            <>
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-sm text-red-700">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
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

              <div className="mt-6 text-center text-sm space-y-2">
                <p>
                  <Link
                    to="/register"
                    className="text-primary-600 hover:text-primary-500 font-medium"
                  >
                    Register as an architect
                  </Link>
                </p>
                <p>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForgot(true);
                      setError('');
                    }}
                    className="text-gray-500 hover:text-gray-700 cursor-pointer"
                  >
                    Forgot your password?
                  </button>
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
