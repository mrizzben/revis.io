import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { listActivity } from '../../api/endpoints/activity';
import Spinner from '../ui/Spinner';

const EVENT_LABELS: Record<string, { label: string; icon: string }> = {
  revision_created: { label: 'Revision uploaded', icon: '⬆️' },
  revision_issued: { label: 'Revision issued to client', icon: '📤' },
  revision_restored: { label: 'Revision restored', icon: '↩️' },
  revision_superseded: { label: 'Revision superseded', icon: '⏭️' },
  revision_archived: { label: 'Revision archived', icon: '🗄️' },
  revision_updated: { label: 'Revision updated', icon: '✏️' },
  comment_created: { label: 'Comment added', icon: '💬' },
  comment_resolved: { label: 'Comment resolved', icon: '✅' },
  comment_reopened: { label: 'Comment reopened', icon: '🔄' },
  review_requested: { label: 'Review requested', icon: '👀' },
  review_approved: { label: 'Review approved', icon: '👍' },
  review_changes_requested: { label: 'Changes requested', icon: '✍️' },
  review_in_review: { label: 'Review started', icon: '🔍' },
  milestone_changed: { label: 'Milestone changed', icon: '📍' },
  file_deleted: { label: 'File deleted', icon: '🗑️' },
  item_forked: { label: 'Item forked into option', icon: '🍴' },
  option_created: { label: 'Design option created', icon: '🧩' },
  option_updated: { label: 'Design option updated', icon: '🧩' },
};

function labelFor(type: string): { label: string; icon: string } {
  return EVENT_LABELS[type] ?? { label: type.replace(/_/g, ' '), icon: '📄' };
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

interface ActivityTimelineProps {
  projectId: number;
}

export default function ActivityTimeline({ projectId }: ActivityTimelineProps) {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ['activity', projectId],
    queryFn: () => listActivity(projectId),
  });

  return (
    <div className="card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <h2 className="text-lg font-semibold text-gray-900">Activity</h2>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="mt-4 space-y-0 max-h-96 overflow-y-auto">
          {isLoading && (
            <div className="flex justify-center py-6">
              <Spinner size="sm" />
            </div>
          )}
          {!isLoading && (!data || data.length === 0) && (
            <p className="text-sm text-gray-400 py-4 text-center">No activity yet.</p>
          )}
          {data?.map((event) => {
            const { label, icon } = labelFor(event.event_type);
            const payload = event.payload as Record<string, unknown>;
            const detail =
              (payload.file_name as string) ||
              (payload.milestone_id ? `Milestone ${payload.milestone_id}` : null) ||
              null;
            return (
              <div key={event.id} className="flex gap-3 py-2.5 border-b border-gray-50 last:border-0">
                <span className="text-base leading-5">{icon}</span>
                <div className="min-w-0">
                  <p className="text-sm text-gray-800">
                    <span className="font-medium">{event.actor?.name ?? 'Someone'}</span> {label.toLowerCase()}
                    {detail ? <span className="text-gray-500"> — {detail}</span> : null}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">{relativeTime(event.created_at)}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
