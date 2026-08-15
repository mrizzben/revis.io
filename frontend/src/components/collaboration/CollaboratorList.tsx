import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  addCollaborator,
  listCollaborators,
  removeCollaborator,
} from '../../api/endpoints/collaborators';
import type { CollaboratorMember } from '../../types';
import Button from '../ui/Button';
import Input from '../ui/Input';

interface CollaboratorListProps {
  projectId: number;
  currentUserId: number;
  currentUserIsOwner: boolean;
}

function CollaboratorRow({
  member,
  removable,
  onRemove,
}: {
  member: CollaboratorMember;
  removable: boolean;
  onRemove: (id: number) => void;
}) {
  return (
    <li className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{member.name}</p>
        <p className="text-xs text-gray-500 truncate">{member.email}</p>
      </div>
      <div className="flex items-center gap-2 ml-3 shrink-0">
        <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-primary-50 text-primary-700 rounded">
          {member.role}
        </span>
        {removable && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRemove(member.user_id)}
            aria-label={`Remove ${member.name}`}
          >
            Remove
          </Button>
        )}
      </div>
    </li>
  );
}

export default function CollaboratorList({
  projectId,
  currentUserId,
  currentUserIsOwner,
}: CollaboratorListProps) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState('');

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['collaborators', projectId],
    queryFn: () => listCollaborators(projectId),
  });

  const addMutation = useMutation({
    mutationFn: (targetEmail: string) => addCollaborator(projectId, { email: targetEmail }),
    onSuccess: () => {
      setEmail('');
      queryClient.invalidateQueries({ queryKey: ['collaborators', projectId] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (userId: number) => removeCollaborator(projectId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collaborators', projectId] });
    },
  });

  if (isLoading) {
    return <p className="text-sm text-gray-500 py-2">Loading collaborators…</p>;
  }

  if (isError || !data) {
    return (
      <div className="py-2">
        <p className="text-sm text-gray-500 mb-2">Could not load collaborators.</p>
        <Button variant="secondary" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (trimmed && !addMutation.isPending) {
      addMutation.mutate(trimmed);
    }
  };

  const handleRemove = (userId: number) => {
    if (userId !== currentUserId && !removeMutation.isPending) {
      removeMutation.mutate(userId);
    }
  };

  return (
    <div>
      {currentUserIsOwner && (
        <form onSubmit={handleSubmit} className="flex gap-2 mb-3">
          <Input
            type="email"
            placeholder="Add teammate by email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1"
            aria-label="Teammate email"
          />
          <Button type="submit" size="sm" isLoading={addMutation.isPending}>
            Add
          </Button>
        </form>
      )}

      <ul>
        {data.owner && (
          <CollaboratorRow
            member={{
              user_id: data.owner.user_id,
              email: data.owner.email,
              name: data.owner.name,
              role: 'owner',
              joined_at: '',
            }}
            removable={false}
            onRemove={() => {}}
          />
        )}
        {data.collaborators.length === 0 && (
          <p className="text-sm text-gray-500 py-2">
            No collaborators yet. Add your team to start working internally.
          </p>
        )}
        {data.collaborators.map((member) => (
          <CollaboratorRow
            key={member.user_id}
            member={member}
            removable={currentUserIsOwner && member.user_id !== currentUserId}
            onRemove={handleRemove}
          />
        ))}
      </ul>
    </div>
  );
}
