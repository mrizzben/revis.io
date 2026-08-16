import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { listActivity } from '../../api/endpoints/activity';
import Icon, { type IconName } from '../ui/icons';
import Spinner from '../ui/Spinner';

const EVENT_ICONS: Record<string, IconName> = {
  revision_created: 'document',
  revision_issued: 'upload',
  revision_restored: 'undo',
  revision_superseded: 'forward',
  revision_archived: 'archive-box',
  revision_updated: 'pencil',
  comment_created: 'chat',
  comment_resolved: 'check-circle',
  comment_reopened: 'refresh',
  review_requested: 'eye',
  review_approved: 'check-circle',
  review_changes_requested: 'pencil-edit',
  review_in_review: 'magnifier',
  milestone_changed: 'map-pin',
  file_deleted: 'trash',
  item_forked: 'fork',
  option_created: 'puzzle',
  option_updated: 'puzzle',
};

const EVENT_LABELS: Record<string, string> = {
  revision_created: 'Revision uploaded',
  revision_issued: 'Revision issued to client',
  revision_restored: 'Revision restored',
  revision_superseded: 'Revision superseded',
  revision_archived: 'Revision archived',
  revision_updated: 'Revision updated',
  comment_created: 'Comment added',
  comment_resolved: 'Comment resolved',
  comment_reopened: 'Comment reopened',
  review_requested: 'Review requested',
  review_approved: 'Review approved',
  review_changes_requested: 'Changes requested',
  review_in_review: 'Review started',
  milestone_changed: 'Milestone changed',
  file_deleted: 'File deleted',
  item_forked: 'Item forked into option',
  option_created: 'Design option created',
  option_updated: 'Design option updated',
};

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
            const label = EVENT_LABELS[event.event_type] ?? event.event_type.replace(/_/g, ' ');
            const icon = EVENT_ICONS[event.event_type] ?? 'document';
            const payload = event.payload as Record<string, unknown>;
            const detail =
              (payload.file_name as string) ||
              (payload.milestone_id ? `Milestone ${payload.milestone_id}` : null) ||
              null;
            return (
              <div key={event.id} className="flex gap-3 py-2.5 border-b border-gray-50 last:border-0">
                <span className="text-gray-400 mt-0.5 flex-shrink-0">
                  <Icon name={icon} className="w-4 h-4" />
                </span>
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
