import { useState, FormEvent, KeyboardEvent } from 'react';
import TextArea from '../ui/TextArea';
import Button from '../ui/Button';

interface CommentFormProps {
  onSubmit: (body: string, parentId?: number) => Promise<void>;
  parentId?: number;
  onCancel?: () => void;
  isLoading?: boolean;
  placeholder?: string;
  replyToName?: string;
}

export default function CommentForm({
  onSubmit,
  parentId,
  onCancel,
  isLoading,
  placeholder,
  replyToName,
}: CommentFormProps) {
  const [body, setBody] = useState('');
  const [error, setError] = useState('');

  const maxLength = 5000;
  const isReply = parentId !== undefined;
  const isDisabled = body.trim().length === 0 || isLoading;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = body.trim();
    if (trimmed.length === 0) {
      setError('Comment cannot be empty.');
      return;
    }
    if (trimmed.length > maxLength) {
      setError(`Comment must be under ${maxLength} characters.`);
      return;
    }
    setError('');
    try {
      await onSubmit(trimmed, parentId);
      setBody('');
    } catch {
      setError('Failed to submit comment. Please try again.');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (!isDisabled) {
        const form = e.currentTarget.closest('form');
        form?.requestSubmit();
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className={isReply ? 'ml-4 border-l-2 border-gray-200 pl-4' : ''}>
      {isReply && replyToName && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-gray-500">
            Replying to <span className="font-medium text-gray-700">{replyToName}</span>
          </span>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              Cancel
            </button>
          )}
        </div>
      )}

      <TextArea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder || (isReply ? 'Write a reply...' : 'Add a comment...')}
        error={error}
        rows={isReply ? 2 : 3}
        className={isReply ? 'text-sm' : ''}
      />

      <div className="flex items-center justify-between mt-2">
        <span className={`text-xs ${body.length > maxLength ? 'text-red-500 font-medium' : 'text-gray-400'}`}>
          {body.length}/{maxLength}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 hidden sm:block">Ctrl+Enter</span>
          <Button
            type="submit"
            size="sm"
            variant={isReply ? 'secondary' : 'primary'}
            disabled={isDisabled}
            isLoading={isLoading}
          >
            {isReply ? 'Reply' : 'Comment'}
          </Button>
        </div>
      </div>
    </form>
  );
}
