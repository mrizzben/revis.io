import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as optionsApi from '../../api/endpoints/activity';
import Badge from '../ui/Badge';
import Spinner from '../ui/Spinner';
import type { DesignFile, DesignOption } from '../../types';

interface OptionsPanelProps {
  projectId: number;
  isOwner: boolean;
  files: DesignFile[];
}

export default function OptionsPanel({ projectId, isOwner, files }: OptionsPanelProps) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [forkTarget, setForkTarget] = useState('');
  const [forkOption, setForkOption] = useState<number | ''>('');

  const { data: options, isLoading } = useQuery({
    queryKey: ['options', projectId],
    queryFn: () => optionsApi.listOptions(projectId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['options', projectId] });
    queryClient.invalidateQueries({ queryKey: ['files'] });
    queryClient.invalidateQueries({ queryKey: ['project'] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      optionsApi.createOption(projectId, { name, description: description || undefined }),
    onSuccess: () => {
      setName('');
      setDescription('');
      setShowForm(false);
      invalidate();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      optionsApi.updateOption(id, data),
    onSuccess: invalidate,
  });

  const forkMutation = useMutation({
    mutationFn: () =>
      optionsApi.forkItem(Number(forkOption), { file_id: forkTarget }),
    onSuccess: () => {
      setForkTarget('');
      setForkOption('');
      invalidate();
    },
  });

  if (isLoading) {
    return (
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Design Options</h2>
        <div className="flex justify-center py-4">
          <Spinner size="sm" />
        </div>
      </div>
    );
  }

  const optionList = options ?? [];
  const showFork = isOwner && optionList.length > 0 && files.length > 0;

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Design Options</h2>
        {isOwner && (
          <button
            onClick={() => setShowForm((v) => !v)}
            className="text-xs text-primary-600 hover:underline"
          >
            {showForm ? 'Cancel' : '+ New option'}
          </button>
        )}
      </div>

      {showForm && isOwner && (
        <div className="mt-3 space-y-2 rounded-lg border border-gray-200 p-3">
          <input
            className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
            placeholder="Option name (e.g. Option A, Courtyard scheme)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <textarea
            className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
            placeholder="Description"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button
            className="px-3 py-1.5 text-xs bg-primary-600 text-white rounded disabled:opacity-40"
            disabled={!name.trim() || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Create option
          </button>
        </div>
      )}

      {!isLoading && optionList.length === 0 && (
        <p className="text-sm text-gray-400 mt-2">
          No design options yet. Create options to explore parallel design directions.
        </p>
      )}

      <div className="mt-3 space-y-2">
        {optionList.map((option: DesignOption) => (
          <div
            key={option.id}
            className={`rounded-lg border p-3 ${option.is_current ? 'border-primary-300 bg-primary-50/40' : option.is_archived ? 'border-gray-100 opacity-60' : 'border-gray-100'}`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-gray-900">{option.name}</span>
                {option.is_current && <Badge variant="success">Current</Badge>}
                {option.is_archived && <Badge className="bg-gray-200 text-gray-500">Archived</Badge>}
                <span className="text-xs text-gray-400">{option.file_count} files</span>
              </div>
            </div>
            {option.description && <p className="text-xs text-gray-600 mt-1">{option.description}</p>}
            {isOwner && (
              <div className="mt-2 flex flex-wrap gap-2">
                {!option.is_current && !option.is_archived && (
                  <button
                    className="text-xs text-green-700 hover:underline disabled:opacity-40"
                    disabled={updateMutation.isPending}
                    onClick={() => updateMutation.mutate({ id: option.id, data: { is_current: true } })}
                  >
                    Set as current
                  </button>
                )}
                {!option.is_archived && (
                  <button
                    className="text-xs text-gray-500 hover:underline disabled:opacity-40"
                    disabled={updateMutation.isPending}
                    onClick={() => {
                      if (confirm('Archive this option? Rejected options stay hidden from clients.')) {
                        updateMutation.mutate({ id: option.id, data: { is_archived: true } });
                      }
                    }}
                  >
                    Archive
                  </button>
                )}
                {option.is_archived && (
                  <button
                    className="text-xs text-gray-500 hover:underline disabled:opacity-40"
                    disabled={updateMutation.isPending}
                    onClick={() => updateMutation.mutate({ id: option.id, data: { is_current: true } })}
                  >
                    Restore
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {showFork && (
        <div className="mt-4 space-y-2 rounded-lg border border-gray-200 p-3">
          <p className="text-xs font-medium text-gray-600">Fork a design item into an option</p>
          <select
            className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
            value={forkTarget}
            onChange={(e) => setForkTarget(e.target.value)}
          >
            <option value="">Select file…</option>
            {files.map((f) => (
              <option key={f.id} value={f.id}>{f.filename}</option>
            ))}
          </select>
          <select
            className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
            value={forkOption}
            onChange={(e) => setForkOption(e.target.value ? Number(e.target.value) : '')}
          >
            <option value="">Into option…</option>
            {optionList.filter((o) => !o.is_archived).map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
          <button
            className="px-3 py-1.5 text-xs bg-primary-600 text-white rounded disabled:opacity-40"
            disabled={!forkTarget || forkOption === '' || forkMutation.isPending}
            onClick={() => forkMutation.mutate()}
          >
            Fork item
          </button>
        </div>
      )}
    </div>
  );
}