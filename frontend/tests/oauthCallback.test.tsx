import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import OAuthCallback from '../src/pages/OAuthCallback';

const navigate = vi.fn();
const login = vi.fn();
const get = vi.fn();

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => navigate,
    useLocation: () => ({
      hash: window.location.hash,
      pathname: '/oauth/callback',
      search: '',
      state: null,
      key: 'default',
    }),
  };
});

vi.mock('../src/api/client', () => ({
  default: { get: (...args: unknown[]) => get(...args) },
}));

vi.mock('../src/stores/authStore', () => ({
  default: () => ({ login }),
}));

describe('OAuthCallback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.location.hash = '';
  });

  it('exchanges the token for a profile and lands on the dashboard', async () => {
    window.location.hash = '#access_token=test-token&token_type=bearer';
    get.mockResolvedValue({ data: { id: 1, email: 'a@b.com', name: 'A' } });

    render(<OAuthCallback />);
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/dashboard', { replace: true }));

    expect(get).toHaveBeenCalledWith('/users/me', {
      headers: { Authorization: 'Bearer test-token' },
    });
    expect(login).toHaveBeenCalledWith('test-token', { id: 1, email: 'a@b.com', name: 'A' });
  });

  it('redirects to login with the error code when Google reports a failure', async () => {
    window.location.hash = '#error=google_oauth_failed';

    render(<OAuthCallback />);
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith('/login?error=google_oauth_failed', { replace: true }),
    );
    expect(get).not.toHaveBeenCalled();
  });

  it('redirects to login when the access token is missing', async () => {
    window.location.hash = '#token_type=bearer';

    render(<OAuthCallback />);
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith('/login?error=google_oauth_failed', { replace: true }),
    );
    expect(get).not.toHaveBeenCalled();
  });
});
