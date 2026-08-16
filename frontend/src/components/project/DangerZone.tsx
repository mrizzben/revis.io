import { useState } from 'react';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Modal from '../ui/Modal';
import type { Project } from '../../types';

interface DangerZoneProps {
  project: Project;
  onArchive: () => Promise<void>;
  onRestore: () => Promise<void>;
  onDelete: () => Promise<void>;
}

type Action = 'archive' | 'restore' | 'delete' | null;

const COPY: Record<Exclude<Action, null>, { title: string; body: string; confirm: string }> = {
  archive: {
    title: 'Archive project',
    body: 'Archiving hides this project from your active list. All files stay in storage and you can restore it anytime.',
    confirm: 'Archive Project',
  },
  restore: {
    title: 'Restore project',
    body: 'This project is currently archived. Restoring brings it back to your active list — all files are still there.',
    confirm: 'Restore Project',
  },
  delete: {
    title: 'Delete project permanently',
    body: 'This will permanently delete the project and remove all files and revisions from storage. This action cannot be undone.',
    confirm: 'Delete Permanently',
  },
};

export default function DangerZone({ project, onArchive, onRestore, onDelete }: DangerZoneProps) {
  const [action, setAction] = useState<Action>(null);
  const [typedName, setTypedName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = (a: Exclude<Action, null>) => {
    setAction(a);
    setTypedName('');
    setError(null);
  };

  const close = () => {
    if (!submitting) setAction(null);
  };

  const handleSubmit = async () => {
    if (!action) return;
    setSubmitting(true);
    setError(null);
    try {
      if (action === 'archive') await onArchive();
      else if (action === 'restore') await onRestore();
      else await onDelete();
      setAction(null);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: unknown } } };
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const copy = action ? COPY[action] : null;
  const needsTypedName = action === 'archive' || action === 'delete';
  const confirmed = !needsTypedName || typedName === project.name;

  return (
    <div className="card border-red-200">
      <h2 className="text-lg font-semibold text-red-700 mb-1">Danger Zone</h2>
      <p className="text-sm text-gray-500 mb-4">
        Archive or permanently delete this project. Deleting removes all files from storage and
        cannot be undone.
      </p>

      <div className="flex flex-wrap gap-3">
        {project.is_archived ? (
          <Button variant="secondary" onClick={() => open('restore')}>
            Restore Project
          </Button>
        ) : (
          <Button variant="secondary" onClick={() => open('archive')}>
            Archive Project
          </Button>
        )}
        <Button variant="danger" onClick={() => open('delete')}>
          Delete Project
        </Button>
      </div>

      <Modal isOpen={action !== null} onClose={close} title={copy?.title}>
        <div className="space-y-4">
          <p className="text-sm text-gray-600">{copy?.body}</p>

          {needsTypedName && (
            <Input
              label={`Type "${project.name}" to confirm`}
              type="text"
              value={typedName}
              onChange={(e) => setTypedName(e.target.value)}
              placeholder={project.name}
            />
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" type="button" onClick={close} disabled={submitting}>
              Cancel
            </Button>
            <Button
              variant={action === 'delete' ? 'danger' : 'primary'}
              type="button"
              onClick={handleSubmit}
              disabled={!confirmed}
              isLoading={submitting}
            >
              {copy?.confirm}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
