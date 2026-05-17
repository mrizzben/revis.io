import { useState } from 'react';
import type { Milestone } from '../../types';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface MilestoneCardProps {
  milestone: Milestone;
  isArchitect?: boolean;
  isCurrent?: boolean;
  onToggle?: (id: number, completed: boolean) => void;
  onEdit?: (milestone: Milestone) => void;
  onDelete?: (id: number) => void;
}

export default function MilestoneCard({
  milestone,
  isArchitect = false,
  isCurrent = false,
  onToggle,
  onEdit,
  onDelete,
}: MilestoneCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const hasLongDescription = (milestone.description?.length ?? 0) > 120;

  const borderColor = milestone.is_completed
    ? 'border-l-green-500'
    : isCurrent
      ? 'border-l-blue-500'
      : 'border-l-gray-300';

  const handleDelete = () => {
    if (confirmDelete) {
      onDelete?.(milestone.id);
      setConfirmDelete(false);
    } else {
      setConfirmDelete(true);
    }
  };

  return (
    <Card padding="md" className={`border-l-4 ${borderColor} ${milestone.is_completed ? 'bg-green-50/30' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className={`text-base font-semibold ${milestone.is_completed ? 'text-green-800' : 'text-gray-900'}`}>
              {milestone.name}
            </h3>
            <Badge variant={milestone.is_completed ? 'success' : isCurrent ? 'info' : 'default'}>
              {milestone.is_completed ? 'Completed' : isCurrent ? 'In Progress' : 'Pending'}
            </Badge>
            <Badge variant="default">{milestone.file_count} files</Badge>
          </div>

          {milestone.description && (
            <div className="mt-1">
              <p
                className={`text-sm text-gray-600 ${!expanded && hasLongDescription ? 'line-clamp-2' : ''}`}
              >
                {milestone.description}
              </p>
              {hasLongDescription && (
                <button
                  type="button"
                  className="text-xs text-primary-600 hover:text-primary-700 mt-0.5"
                  onClick={() => setExpanded(!expanded)}
                >
                  {expanded ? 'Show less' : 'Show more'}
                </button>
              )}
            </div>
          )}

          {milestone.is_completed && milestone.completed_at && (
            <div className="mt-2 flex items-center gap-1 text-xs text-green-700">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>
                Completed {new Date(milestone.completed_at).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </span>
            </div>
          )}
        </div>

        {isArchitect && (
          <div className="flex items-center gap-1 shrink-0">
            <label className="flex items-center gap-1.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={milestone.is_completed}
                onChange={(e) => onToggle?.(milestone.id, e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-xs text-gray-500">Done</span>
            </label>

            <button
              type="button"
              onClick={() => onEdit?.(milestone)}
              className="p-1 text-gray-400 hover:text-primary-600 rounded transition-colors"
              title="Edit milestone"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </button>

            <button
              type="button"
              onClick={handleDelete}
              className={`p-1 rounded transition-colors ${
                confirmDelete
                  ? 'text-red-600 bg-red-50'
                  : 'text-gray-400 hover:text-red-600'
              }`}
              title={confirmDelete ? 'Click again to confirm' : 'Delete milestone'}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}
