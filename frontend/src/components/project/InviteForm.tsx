import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import * as projectsApi from '../../api/endpoints/projects';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Badge from '../ui/Badge';

interface InviteFormProps {
  projectId: number;
}

export default function InviteForm({ projectId }: InviteFormProps) {
  const [email, setEmail] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const inviteMutation = useMutation({
    mutationFn: (inviteEmail: string) =>
      projectsApi.inviteClient(projectId, { email: inviteEmail }),
    onSuccess: () => {
      setSuccessMessage(`Invitation sent to ${email}`);
      setEmail('');
      setTimeout(() => setSuccessMessage(''), 5000);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    inviteMutation.mutate(email);
  };

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4">Invite Client</h2>
      <p className="text-sm text-gray-500 mb-4">
        Send an invitation email to a client. They'll create an account and get access to this project.
      </p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="client@example.com"
          required
        />
        <Button
          type="submit"
          isLoading={inviteMutation.isPending}
          className="w-full"
        >
          Send Invitation
        </Button>
      </form>
      {inviteMutation.isError && (
        <p className="mt-3 text-sm text-red-600">
          {(inviteMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            'Failed to send invitation'}
        </p>
      )}
      {successMessage && (
        <p className="mt-3 text-sm text-green-600">{successMessage}</p>
      )}
    </div>
  );
}
