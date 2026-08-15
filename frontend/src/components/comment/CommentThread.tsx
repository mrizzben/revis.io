import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Comment } from '../../types';
import { listComments, createComment, updateComment, deleteComment } from '../../api/endpoints/comments';
import CommentItem from './CommentItem';
import CommentForm from './CommentForm';

interface CommentThreadProps {
  fileId: string;
  projectId: number;
  currentUserId: number;
  isArchitect?: boolean;
  // Scope comments to a specific revision (T1); omit for all-revision comments.
  versionId?: number | null;
}

export default function CommentThread({
  fileId,
  projectId: _projectId,
  currentUserId,
  isArchitect = false,
  versionId = null,
}: CommentThreadProps) {
  const queryClient = useQueryClient();
  const [replyingTo, setReplyingTo] = useState<number | null>(null);
  const [editingComment, setEditingComment] = useState<number | null>(null);
  const [editBody, setEditBody] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const {
    data: comments,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['comments', fileId],
    queryFn: () => listComments(fileId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['comments', fileId] });
    queryClient.invalidateQueries({ queryKey: ['files'] });
  };

  const handleCreate = async (body: string, parentId?: number) => {
    setSubmitting(true);
    try {
      await createComment(fileId, { body, parent_id: parentId, version_id: versionId });
      setReplyingTo(null);
      invalidate();
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (commentId: number, body: string) => {
    setEditingComment(commentId);
    setEditBody(body);
  };

  const handleSaveEdit = async () => {
    if (!editingComment || editBody.trim().length === 0) return;
    setSubmitting(true);
    try {
      await updateComment(editingComment, { body: editBody.trim() });
      setEditingComment(null);
      setEditBody('');
      invalidate();
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelEdit = () => {
    setEditingComment(null);
    setEditBody('');
  };

  const handleDelete = async (commentId: number) => {
    try {
      await deleteComment(commentId);
      invalidate();
    } catch {
      // silent
    }
  };

  const handleResolve = async (commentId: number, resolved: boolean) => {
    try {
      await updateComment(commentId, { is_resolved: resolved });
      invalidate();
    } catch {
      // silent
    }
  };

  const findReplyToName = (parentId: number): string => {
    if (!comments) return '';
    const find = (list: Comment[]): string | null => {
      for (const c of list) {
        if (c.id === parentId) return c.author.name;
        const found = find(c.replies || []);
        if (found) return found;
      }
      return null;
    };
    return find(comments) || '';
  };

  if (isLoading) {
    return (
      <div className="space-y-4 py-2">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <svg className="w-10 h-10 text-gray-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <p className="text-sm text-gray-500">Failed to load comments</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          Retry
        </button>
      </div>
    );
  }

  const sorted = comments || [];
  const isEmpty = sorted.length === 0;

  return (
    <div className="space-y-4">
      <CommentForm
        onSubmit={handleCreate}
        isLoading={submitting && replyingTo === null}
      />

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <svg className="w-10 h-10 text-gray-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <p className="text-sm text-gray-500">No comments yet. Be the first to share feedback.</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-100">
          {sorted.map((comment) => (
            <div key={comment.id}>
              <CommentItem
                comment={comment}
                currentUserId={currentUserId}
                isArchitect={isArchitect}
                onReply={setReplyingTo}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onResolve={handleResolve}
                isEditing={editingComment === comment.id}
                editBody={editBody}
                onEditBodyChange={setEditBody}
                onSaveEdit={handleSaveEdit}
                onCancelEdit={handleCancelEdit}
              />

              {replyingTo === comment.id && (
                <div className="py-2">
                  <CommentForm
                    onSubmit={handleCreate}
                    parentId={comment.id}
                    replyToName={comment.author.name}
                    onCancel={() => setReplyingTo(null)}
                    isLoading={submitting}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
