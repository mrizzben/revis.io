import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { listInternalNotes } from '../../api/endpoints/internalNotes';
import { createInternalNote, createInternalNoteReply } from '../../api/endpoints/internalNotes';
import type { CollaboratorMember, InternalNote } from '../../types';
import Button from '../ui/Button';
import TextArea from '../ui/TextArea';

interface InternalNoteListProps {
  projectId: number;
  collaborators: CollaboratorMember[];
}

function NoteCard({ note, projectId }: { note: InternalNote; projectId: number }) {
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyBody, setReplyBody] = useState('');
  const queryClient = useQueryClient();

  const replyMutation = useMutation({
    mutationFn: (body: string) => createInternalNoteReply(projectId, note.id, body),
    onSuccess: () => {
      setReplyBody('');
      setReplyOpen(false);
      queryClient.invalidateQueries({ queryKey: ['internal-notes'] });
    },
  });

  return (
    <div className="py-3 border-b border-border last:border-0">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-medium text-gray-900">
          {note.author?.name ?? 'Team member'}
        </span>
        <span className="text-xs text-gray-400">{new Date(note.created_at).toLocaleString()}</span>
      </div>
      <p className="text-sm text-gray-700 whitespace-pre-wrap">{note.body}</p>
      {note.mentions.length > 0 && (
        <p className="mt-1 text-xs text-primary-600">
          Mentioned: {note.mentions.map((m) => `@${m.name}`).join(', ')}
        </p>
      )}

      {note.replies.map((r) => (
        <div key={r.id} className="ml-4 mt-2 p-2 bg-gray-50 rounded">
          <p className="text-xs text-gray-500">{r.author?.name ?? 'Team member'}</p>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{r.body}</p>
        </div>
      ))}

      <Button variant="ghost" size="sm" className="mt-2" onClick={() => setReplyOpen((v) => !v)}>
        {replyOpen ? 'Cancel' : 'Reply'}
      </Button>

      {replyOpen && (
        <form
          className="mt-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (replyBody.trim() && !replyMutation.isPending) {
              replyMutation.mutate(replyBody.trim());
            }
          }}
        >
          <TextArea
            value={replyBody}
            onChange={(e) => setReplyBody(e.target.value)}
            placeholder="Write an internal reply…"
            className="min-h-[60px]"
          />
          <Button type="submit" size="sm" className="mt-1" isLoading={replyMutation.isPending}>
            Reply
          </Button>
        </form>
      )}
    </div>
  );
}

export default function InternalNoteList({ projectId, collaborators }: InternalNoteListProps) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState('');
  const [mentionIds, setMentionIds] = useState<number[]>([]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['internal-notes', projectId],
    queryFn: () => listInternalNotes(projectId),
  });

  const createMutation = useMutation({
    mutationFn: () => createInternalNote(projectId, { body, mentions: mentionIds }),
    onSuccess: () => {
      setBody('');
      setMentionIds([]);
      queryClient.invalidateQueries({ queryKey: ['internal-notes', projectId] });
    },
  });

  const toggleMention = (id: number) => {
    setMentionIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  if (isLoading) {
    return <p className="text-sm text-gray-500 py-2">Loading notes…</p>;
  }

  if (isError || !data) {
    return (
      <div className="py-2">
        <p className="text-sm text-gray-500 mb-2">Could not load internal notes.</p>
        <Button variant="secondary" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const notes = data.notes;

  return (
    <div>
      {collaborators.length > 0 && (
        <form
          className="mb-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (body.trim() && !createMutation.isPending) {
              createMutation.mutate();
            }
          }}
        >
          <TextArea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Write an internal note… (visible only to your team)"
            className="min-h-[80px]"
          />
          {collaborators.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <span className="text-xs text-gray-500">Mention:</span>
              {collaborators.map((c) => (
                <button
                  key={c.user_id}
                  type="button"
                  onClick={() => toggleMention(c.user_id)}
                  className={`px-2 py-0.5 text-xs font-medium rounded border transition ${
                    mentionIds.includes(c.user_id)
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white text-gray-600 border-border hover:bg-gray-50'
                  }`}
                >
                  @{c.name}
                </button>
              ))}
            </div>
          )}
          <Button type="submit" size="sm" className="mt-2" isLoading={createMutation.isPending}>
            Add note
          </Button>
        </form>
      )}

      {notes.length === 0 && (
        <p className="text-sm text-gray-500 py-2">
          No internal notes yet. Notes here are private to your team.
        </p>
      )}
      {notes.map((note) => (
        <NoteCard key={note.id} note={note} projectId={projectId} />
      ))}
    </div>
  );
}
