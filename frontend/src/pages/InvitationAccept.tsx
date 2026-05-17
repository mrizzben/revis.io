import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import * as projectsApi from '../api/endpoints/projects';
import Spinner from '../components/ui/Spinner';
import Button from '../components/ui/Button';
import type { InvitationDetail } from '../types';

export default function InvitationAccept() {
  const { token } = useParams<{ token: string }>();
  const [invitation, setInvitation] = useState<InvitationDetail | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadInvitation() {
      if (!token) {
        setError('No invitation token provided');
        setIsLoading(false);
        return;
      }

      try {
        const data = await projectsApi.getInvitation(token);
        setInvitation(data);
      } catch {
        setError('This invitation is invalid or has expired');
      } finally {
        setIsLoading(false);
      }
    }

    loadInvitation();
  }, [token]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !invitation) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="card max-w-md w-full text-center">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Invitation Error</h2>
          <p className="text-gray-600 mb-6">{error || 'Invitation not found'}</p>
          <Link to="/login">
            <Button variant="secondary">Go to Login</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="card max-w-md w-full text-center">
        <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        </div>

        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          You're Invited!
        </h2>
        <p className="text-gray-600 mb-1">
          <strong>{invitation.invited_by_name}</strong> has invited you to collaborate on
        </p>
        <p className="text-lg font-medium text-primary-600 mb-6">
          {invitation.project_name}
        </p>

        <p className="text-sm text-gray-500 mb-6">
          Create a client account to accept this invitation and access the project.
        </p>

        <Link to={`/register?token=${token}`}>
          <Button className="w-full">Accept & Create Account</Button>
        </Link>

        <p className="mt-4 text-sm text-gray-500">
          Already have an account?{' '}
          <Link to="/login" className="text-primary-600 hover:text-primary-500 font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
