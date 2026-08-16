import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { deleteTodo, updateTodo } from '../../api/endpoints/todos';
import type { ToDo } from '../../types';

interface TodoCardProps {
  todo: ToDo;
  projectId: number;
}

export default function TodoCard({ todo, projectId }: TodoCardProps) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const toggleStatus = useMutation({
    mutationFn: (status: 'open' | 'complete') => updateTodo(projectId, todo.id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos', projectId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteTodo(projectId, todo.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos', projectId] });
    },
  });

  const isComplete = todo.status === 'complete';

  return (
    <div className={`py-3 border-b border-border last:border-0 ${isComplete ? 'opacity-60' : ''}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            role="checkbox"
            aria-checked={isComplete}
            onClick={() => toggleStatus.mutate(isComplete ? 'open' : 'complete')}
            className={`w-5 h-5 shrink-0 rounded border transition flex items-center justify-center ${
              isComplete
                ? 'bg-primary-600 border-primary-600 text-white'
                : 'bg-white border-border hover:border-primary-500'
            }`}
            aria-label={isComplete ? 'Mark as open' : 'Mark as complete'}
          >
            {isComplete && (
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
          </button>
          <div className="min-w-0">
            <p
              className={`text-sm font-medium ${isComplete ? 'line-through text-gray-400' : 'text-gray-900'}`}
            >
              {todo.title}
            </p>
            {todo.assignee && (
              <p className="text-xs text-gray-500">Assignee: {todo.assignee.name}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            className="text-xs text-gray-400 hover:text-gray-600"
            onClick={() => setExpanded((v) => !v)}
            aria-label="Toggle details"
          >
            {expanded ? 'Hide' : 'Details'}
          </button>
          <button
            type="button"
            className="text-xs text-red-500 hover:text-red-700"
            onClick={() => {
              if (confirm(`Delete "${todo.title}"? This cannot be undone.`)) {
                deleteMutation.mutate();
              }
            }}
            aria-label={`Delete ${todo.title}`}
          >
            Delete
          </button>
        </div>
      </div>
      {expanded && (
        <div className="mt-2 text-sm text-gray-600">
          {todo.description ? (
            <p className="whitespace-pre-wrap">{todo.description}</p>
          ) : (
            <p className="text-gray-400">No description</p>
          )}
          <p className="text-xs text-gray-400 mt-1">
            {todo.created_by ? `Created by ${todo.created_by.name}` : 'Team'} ·{' '}
            {new Date(todo.created_at).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}
