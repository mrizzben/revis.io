import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as reviewsApi from '../../api/endpoints/reviews';
import Badge from '../ui/Badge';
import Spinner from '../ui/Spinner';
import type { Review, ReviewStatus, UserBrief } from '../../types';

const STATUS_LABELS: Record<ReviewStatus, string> = {
  draft: 'Draft',
  in_review: 'In review',
  changes_requested: 'Changes requested',
  approved: 'Approved',
};

const STATUS_CLASSES: Record<ReviewStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  in_review: 'bg-amber-100 text-amber-700',
  changes_requested: 'bg-red-100 text-red-700',
  approved: 'bg-green-100 text-green-700',
};

interface ReviewPanelProps {
  fileId: string;
  projectId: number;
  collaborators: UserBrief[];
  isClientReview?: boolean;
}

export default function ReviewPanel({
  fileId,
  projectId,
  collaborators,
  isClientReview = false,
}: ReviewPanelProps) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [reviewerId, setReviewerId] = useState<number | ''>('');
  const [note, setNote] = useState('');
  const [decisionComment, setDecisionComment] = useState('');

  const { data: reviews, isLoading } = useQuery({
    queryKey: ['reviews', fileId],
    queryFn: () => reviewsApi.listReviews(fileId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['reviews', fileId] });
    queryClient.invalidateQueries({ queryKey: ['activity', projectId] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      reviewsApi.createReview(fileId, {
        reviewer_id: Number(reviewerId),
        is_client_review: isClientReview,
        note: note || undefined,
      }),
    onSuccess: () => {
      setShowForm(false);
      setReviewerId('');
      setNote('');
      invalidate();
    },
  });

  const transitionMutation = useMutation({
    mutationFn: ({ id, action, comment }: { id: number; action: 'start' | 'approve' | 'request_changes'; comment?: string }) =>
      reviewsApi.transitionReview(id, { action, comment }),
    onSuccess: () => {
      setDecisionComment('');
      invalidate();
    },
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-900">
          {isClientReview ? 'Client Review' : 'Reviews'}
        </h4>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="text-xs text-primary-600 hover:underline"
        >
          {showForm ? 'Cancel' : '+ Request review'}
        </button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-gray-200 p-3 space-y-2">
          <select
            className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value ? Number(e.target.value) : '')}
          >
            <option value="">Assign reviewer…</option>
            {collaborators.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <input
            className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
            placeholder="Note for the reviewer"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            className="px-3 py-1.5 text-xs bg-primary-600 text-white rounded disabled:opacity-40"
            disabled={!reviewerId || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? 'Requesting…' : 'Request review'}
          </button>
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-4">
          <Spinner size="sm" />
        </div>
      )}

      {!isLoading && (!reviews || reviews.length === 0) && (
        <p className="text-xs text-gray-400">
          {isClientReview
            ? 'No client review opened for this file yet.'
            : 'No reviews requested yet.'}
        </p>
      )}

      {reviews?.map((r: Review) => (
        <div key={r.id} className="rounded-lg border border-gray-100 p-3 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge className={STATUS_CLASSES[r.status]}>{STATUS_LABELS[r.status]}</Badge>
              {r.revision_number && <span className="text-xs text-gray-500">v{r.revision_number}</span>}
            </div>
            <span className="text-xs text-gray-400">{new Date(r.created_at).toLocaleDateString()}</span>
          </div>
          <p className="text-xs text-gray-600">
            <span className="font-medium">{r.requested_by?.name}</span> requested review from{' '}
            <span className="font-medium">{r.reviewer?.name}</span>
          </p>
          {r.decision_comment && (
            <p className="text-xs italic text-gray-700">“{r.decision_comment}”</p>
          )}
          {r.decided_by && r.decided_at && (
            <p className="text-xs text-gray-400">
              Decided by {r.decided_by.name} on {new Date(r.decided_at).toLocaleString()}
            </p>
          )}
          {(r.status === 'draft' || r.status === 'changes_requested') && (
            <div className="pt-1 flex flex-wrap gap-2">
              <button
                className="text-xs text-primary-600 hover:underline disabled:opacity-40"
                disabled={transitionMutation.isPending}
                onClick={() => transitionMutation.mutate({ id: r.id, action: 'start' })}
              >
                Start review
              </button>
            </div>
          )}
          {r.status === 'in_review' && (
            <div className="pt-1 space-y-1">
              <input
                className="border border-gray-300 rounded px-2 py-1 text-xs w-full"
                placeholder="Decision comment…"
                value={decisionComment}
                onChange={(e) => setDecisionComment(e.target.value)}
              />
              <div className="flex gap-2">
                <button
                  className="text-xs text-green-700 hover:underline disabled:opacity-40"
                  disabled={transitionMutation.isPending}
                  onClick={() =>
                    transitionMutation.mutate({
                      id: r.id,
                      action: 'approve',
                      comment: decisionComment || undefined,
                    })
                  }
                >
                  ✓ Approve
                </button>
                <button
                  className="text-xs text-red-700 hover:underline disabled:opacity-40"
                  disabled={transitionMutation.isPending}
                  onClick={() =>
                    transitionMutation.mutate({
                      id: r.id,
                      action: 'request_changes',
                      comment: decisionComment || undefined,
                    })
                  }
                >
                  ✗ Request changes
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
