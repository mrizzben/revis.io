import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { createTodo, listTodos } from '../../api/endpoints/todos';
import type { CollaboratorMember, ToDo } from '../../types';
import CollaboratorList from './CollaboratorList';
import InternalNoteList from './InternalNoteList';
import TodoCard from './TodoCard';
import Button from '../ui/Button';
import Input from '../ui/Input';

interface InternalPanelProps {
  projectId: number;
  currentUserId: number;
  currentUserIsOwner: boolean;
  collaborators: CollaboratorMember[];
}

export default function InternalPanel({
  projectId,
  currentUserId,
  currentUserIsOwner,
  collaborators,
}: InternalPanelProps) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<'notes' | 'todos' | 'members'>('notes');
  const [todoTitle, setTodoTitle] = useState('');
  const [todoAssignee, setTodoAssignee] = useState<number | ''>('');

  const { data: todos } = useQuery({
    queryKey: ['todos', projectId],
    queryFn: () => listTodos(projectId),
  });

  const createTodoMutation = useMutation({
    mutationFn: () =>
      createTodo(projectId, {
        title: todoTitle,
        assignee_id: todoAssignee === '' ? null : Number(todoAssignee),
      }),
    onSuccess: () => {
      setTodoTitle('');
      setTodoAssignee('');
      queryClient.invalidateQueries({ queryKey: ['todos', projectId] });
    },
  });

  const handleCreateTodo = (e: React.FormEvent) => {
    e.preventDefault();
    if (todoTitle.trim() && !createTodoMutation.isPending) {
      createTodoMutation.mutate();
    }
  };

  return (
    <div className="card mt-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-bold text-gray-900">Internal team</h2>
        <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-amber-50 text-amber-700 rounded">
          Team only — hidden from clients
        </span>
      </div>

      <div className="flex gap-1 mb-4 border-b border-border">
        {(
          [
            ['notes', 'Notes'],
            ['todos', 'To-dos'],
            ['members', 'Members'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              tab === key
                ? 'border-primary-600 text-primary-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'members' && (
        <CollaboratorList
          projectId={projectId}
          currentUserId={currentUserId}
          currentUserIsOwner={currentUserIsOwner}
        />
      )}

      {tab === 'notes' && <InternalNoteList projectId={projectId} collaborators={collaborators} />}

      {tab === 'todos' && (
        <div>
          <form onSubmit={handleCreateTodo} className="flex flex-col sm:flex-row gap-2 mb-3">
            <Input
              placeholder="New to-do…"
              value={todoTitle}
              onChange={(e) => setTodoTitle(e.target.value)}
              className="flex-1"
              aria-label="To-do title"
            />
            <select
              value={todoAssignee}
              onChange={(e) => setTodoAssignee(e.target.value === '' ? '' : Number(e.target.value))}
              className="input-field w-auto"
              aria-label="Assignee"
            >
              <option value="">Unassigned</option>
              {collaborators.map((c) => (
                <option key={c.user_id} value={c.user_id}>
                  {c.name}
                </option>
              ))}
            </select>
            <Button type="submit" size="sm" isLoading={createTodoMutation.isPending}>
              Add
            </Button>
          </form>

          {!todos || todos.length === 0 ? (
            <p className="text-sm text-gray-500 py-2">No to-dos yet. Assign tasks to your team.</p>
          ) : (
            todos.map((todo: ToDo) => <TodoCard key={todo.id} todo={todo} projectId={projectId} />)
          )}
        </div>
      )}
    </div>
  );
}
