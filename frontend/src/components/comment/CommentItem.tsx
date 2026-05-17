import { useState } from 'react';
import { Comment } from '../../types';
import Badge from '../ui/Badge';
import Button from '../ui/Button';

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function nameHash(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return hash;
}

const AVATAR_COLORS = [
  'bg-blue-500',
  'bg-green-500',
  'bg-purple-500',
  'bg-orange-500',
  'bg-pink-500',
  'bg-teal-500',
  'bg-indigo-500',
  'bg-red-500',
];

function getAvatarColor(name: string): string {
  const idx = Math.abs(nameHash(name)) % AVATAR_COLORS.length;
  return AVATAR_COLORS[idx];
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

interface CommentItemProps {
  comment: Comment;
  currentUserId: number;
  isArchitect?: boolean;
  onReply: (parentId: number) => void;
  onEdit: (commentId: number, body: string) => void;
  onDelete: (commentId: number) => void;
  onResolve: (commentId: number, resolved: boolean) => void;
  depth?: number;
  isEditing?: boolean;
  editBody?: string;
  onEditBodyChange?: (body: string) => void;
  onSaveEdit?: () => void;
  onCancelEdit?: () => void;
}

export default function CommentItem({
  comment,
  currentUserId,
  isArchitect = false,
  onReply,
  onEdit,
  onDelete,
  onResolve,
  depth = 0,
  isEditing = false,
  editBody = '',
  onEditBodyChange,
  onSaveEdit,
  onCancelEdit,
}: CommentItemProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const isDeleted = comment.body === '[deleted]';
  const isOwn = currentUserId === comment.author.id;
  const avatarColor = getAvatarColor(comment.author.name);
  const initials = getInitials(comment.author.name);

  const renderBody = () => {
    if (isDeleted) {
      return <p className="text-sm text-gray-400 italic">This comment was deleted.</p>;
    }

    if (isEditing) {
      return (
        <div className="mt-1">
          <textarea
            value={editBody}
            onChange={(e) => onEditBodyChange?.(e.target.value)}
            className="input-field resize-y min-h-[60px] w-full text-sm"
            rows={2}
          />
          <div className="flex items-center gap-2 mt-1.5">
            <Button size="sm" onClick={onSaveEdit}>
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancelEdit}>
              Cancel
            </Button>
          </div>
        </div>
      );
    }

    return (
      <p className="text-sm text-gray-700 whitespace-pre-wrap break-words">
        {comment.body}
      </p>
    );
  };

  return (
    <div className={`${depth > 0 ? `border-l-2 border-gray-200` : ''}`}>
      <div className={`${depth > 0 ? 'ml-4' : ''} py-2`}>
        <div className="flex gap-3">
          {/* Avatar */}
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white text-xs font-semibold ${avatarColor}`}
          >
            {initials}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold text-gray-900">
                {comment.author.name}
              </span>
              {comment.author.role === 'architect' && (
                <Badge variant="info">Architect</Badge>
              )}
              {comment.author.role === 'client' && (
                <Badge>Client</Badge>
              )}
              <span className="text-xs text-gray-400">
                {timeAgo(comment.created_at)}
              </span>
            </div>

            {/* Body */}
            <div className="mt-1">{renderBody()}</div>

            {/* Actions */}
            {!isDeleted && (
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => onReply(comment.id)}
                  className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  Reply
                </button>

                {isOwn && !isEditing && (
                  <>
                    <button
                      type="button"
                      onClick={() => onEdit(comment.id, comment.body)}
                      className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      Edit
                    </button>
                    {confirmDelete ? (
                      <span className="text-xs">
                        <button
                          type="button"
                          onClick={() => {
                            onDelete(comment.id);
                            setConfirmDelete(false);
                          }}
                          className="text-red-500 hover:text-red-700 font-medium"
                        >
                          Confirm
                        </button>
                        <span className="text-gray-300 mx-1">|</span>
                        <button
                          type="button"
                          onClick={() => setConfirmDelete(false)}
                          className="text-gray-400 hover:text-gray-600"
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmDelete(true)}
                        className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                      >
                        Delete
                      </button>
                    )}
                  </>
                )}

                {isArchitect && !isEditing && (
                  <label className="inline-flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer ml-1">
                    <input
                      type="checkbox"
                      checked={comment.is_resolved}
                      onChange={(e) => onResolve(comment.id, e.target.checked)}
                      className="w-3.5 h-3.5 rounded border-gray-300 text-green-600 focus:ring-green-500"
                    />
                    {comment.is_resolved ? (
                      <span className="text-green-600 font-medium">Resolved</span>
                    ) : (
                      'Mark resolved'
                    )}
                  </label>
                )}
              </div>
            )}

            {/* Resolved badge */}
            {comment.is_resolved && !isEditing && !isDeleted && (
              <div className="mt-1">
                <Badge variant="success">Resolved</Badge>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Replies */}
      {comment.replies && comment.replies.length > 0 && (
        <div className={depth > 0 ? '' : 'ml-4'}>
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              currentUserId={currentUserId}
              isArchitect={isArchitect}
              onReply={onReply}
              onEdit={onEdit}
              onDelete={onDelete}
              onResolve={onResolve}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
