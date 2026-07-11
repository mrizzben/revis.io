import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import * as authApi from '../api/endpoints/auth';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import apiClient from '../api/client';

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
          storeLogin(tokens.access_token, null);
          const user = await apiClient.get('/users/me', {
            headers: { Authorization: `Bearer ${tokens.access_token}` }
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
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Registration failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-secondary px-4">
      <div className="max-w-sm w-full">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <svg className="w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Revis.io</h1>
          </div>
          <p className="text-sm text-gray-500">Create your account</p>
        </div>

        <div className="border border-border bg-white p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
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