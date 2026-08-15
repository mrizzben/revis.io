import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as filesApi from '../../api/endpoints/files';
import Badge from '../ui/Badge';
import Spinner from '../ui/Spinner';
import type { DesignFile, FileVersion } from '../../types';

const VISIBILITY_LABELS: Record<string, { label: string; className: string }> = {
  internal: { label: 'Draft', className: 'bg-gray-100 text-gray-700' },
  review: { label: 'In review', className: 'bg-amber-100 text-amber-700' },
  client_issued: { label: 'Issued', className: 'bg-green-100 text-green-700' },
  superseded: { label: 'Superseded', className: 'bg-yellow-100 text-yellow-700' },
  archived: { label: 'Archived', className: 'bg-gray-200 text-gray-500' },
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const val = bytes / Math.pow(1024, i);
  return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

interface MilestoneBrief {
  id: number;
  name: string;
}

interface RevisionPanelProps {
  file: DesignFile;
  isArchitect: boolean;
  milestones?: MilestoneBrief[];
  onOpenCompare: (from: FileVersion, to: FileVersion) => void;
}

export default function RevisionPanel({
  file,
  isArchitect,
  milestones,
  onOpenCompare,
}: RevisionPanelProps) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(true);
  const [editing, setEditing] = useState<FileVersion | null>(null);
  const [metaForm, setMetaForm] = useState<{ name: string; description: string; revision_message: string; milestone_id: number | '' }>({
    name: '',
    description: '',
    revision_message: '',
    milestone_id: '',
  });

  const { data: versions, isLoading } = useQuery({
    queryKey: ['versions', file.id],
    queryFn: () => filesApi.listVersions(file.id),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['versions', file.id] });
    queryClient.invalidateQueries({ queryKey: ['files'] });
    queryClient.invalidateQueries({ queryKey: ['project'] });
  };

  const restoreMutation = useMutation({
    mutationFn: (v: number) => filesApi.restoreVersion(file.id, v),
    onSuccess: invalidate,
  });
  const issueMutation = useMutation({
    mutationFn: (v: number) => filesApi.issueVersion(file.id, v),
    onSuccess: invalidate,
  });
  const supersedeMutation = useMutation({
    mutationFn: (v: number) => filesApi.supersedeVersion(file.id, v),
    onSuccess: invalidate,
  });
  const archiveMutation = useMutation({
    mutationFn: (v: number) => filesApi.archiveVersion(file.id, v),
    onSuccess: invalidate,
  });
  const reviewStateMutation = useMutation({
    mutationFn: ({ v, inReview }: { v: number; inReview: boolean }) =>
      filesApi.setVersionReview(file.id, v, inReview),
    onSuccess: invalidate,
  });
  const metaMutation = useMutation({
    mutationFn: ({ v, data }: { v: number; data: object }) =>
      filesApi.updateVersionMeta(file.id, v, data),
    onSuccess: () => {
      setEditing(null);
      invalidate();
    },
  });

  const handleDownload = (v: FileVersion) => {
    if (v.download_url) window.open(v.download_url, '_blank');
  };

  const openEdit = (v: FileVersion) => {
    setEditing(v);
    setMetaForm({
      name: v.name ?? '',
      description: v.description ?? '',
      revision_message: v.revision_message ?? '',
      milestone_id: v.milestone_id ?? '',
    });
  };

  const saveMeta = (v: FileVersion) => {
    metaMutation.mutate({
      v: v.version_number,
      data: {
        name: metaForm.name || null,
        description: metaForm.description || null,
        revision_message: metaForm.revision_message || null,
        milestone_id: metaForm.milestone_id === '' ? null : Number(metaForm.milestone_id),
      },
    });
  };

  const sorted = [...(versions ?? [])].sort((a, b) => b.version_number - a.version_number);

  return (
    <div className="border-t border-gray-100 pt-3">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between text-sm font-medium text-gray-700 hover:text-gray-900"
      >
        <span>Revisions ({file.version_count ?? versions?.length ?? 0})</span>
        <svg
          className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {isLoading && (
            <div className="flex justify-center py-4">
              <Spinner size="sm" />
            </div>
          )}
          {!isLoading && (!sorted || sorted.length === 0) && (
            <p className="text-xs text-gray-400 py-2">No revisions yet.</p>
          )}
          {sorted.map((v) => {
            const badge = VISIBILITY_LABELS[v.visibility] ?? VISIBILITY_LABELS.internal;
            const isCurrent = v.is_current;
            const busy =
              restoreMutation.isPending ||
              issueMutation.isPending ||
              supersedeMutation.isPending ||
              archiveMutation.isPending;
            return (
              <div
                key={v.id}
                className={`rounded-lg border p-3 ${isCurrent ? 'border-primary-300 bg-primary-50/40' : 'border-gray-100'}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900">
                      v{v.version_number}
                    </span>
                    <Badge className={badge.className}>{badge.label}</Badge>
                    {isCurrent && <Badge variant="info">Current</Badge>}
                    {v.restored_from_superseded && (
                      <Badge className="bg-purple-100 text-purple-700">Restored</Badge>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">
                    {new Date(v.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="mt-1 text-xs text-gray-600 space-y-0.5">
                  {v.name && (
                    <p className="font-medium text-gray-800">📌 {v.name}</p>
                  )}
                  {v.description && <p>{v.description}</p>}
                  {v.revision_message && <p className="italic">"{v.revision_message}"</p>}
                  <p>
                    by {v.uploaded_by?.name ?? 'Unknown'} · {formatBytes(v.file_size)}
                    {v.milestone_name ? ` · ${v.milestone_name}` : ''}
                  </p>
                  {v.issued_at && v.issued_by && (
                    <p className="text-green-700">
                      Issued by {v.issued_by.name} on {new Date(v.issued_at).toLocaleString()}
                    </p>
                  )}
                  {v.content_hash && (
                    <p className="text-gray-400 font-mono" title="Content hash (SHA-256)">
                      sha256:{v.content_hash.slice(0, 12)}…
                    </p>
                  )}
                  {v.scan_status === 'infected' && (
                    <p className="text-red-600 font-medium">⚠ Malware scan failed — cannot issue</p>
                  )}
                </div>

                {editing?.id === v.id ? (
                  <div className="mt-2 space-y-2">
                    <input
                      className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
                      placeholder="Checkpoint name (e.g. Planning submission)"
                      value={metaForm.name}
                      onChange={(e) => setMetaForm({ ...metaForm, name: e.target.value })}
                    />
                    <textarea
                      className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
                      placeholder="Description / issue note"
                      rows={2}
                      value={metaForm.description}
                      onChange={(e) => setMetaForm({ ...metaForm, description: e.target.value })}
                    />
                    <input
                      className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
                      placeholder="Change message"
                      value={metaForm.revision_message}
                      onChange={(e) => setMetaForm({ ...metaForm, revision_message: e.target.value })}
                    />
                    {milestones && (
                      <select
                        className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
                        value={metaForm.milestone_id}
                        onChange={(e) =>
                          setMetaForm({
                            ...metaForm,
                            milestone_id: e.target.value ? Number(e.target.value) : '',
                          })
                        }
                      >
                        <option value="">No milestone</option>
                        {milestones.map((m) => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                      </select>
                    )}
                    <div className="flex gap-2">
                      <button
                        className="px-2 py-1 text-xs bg-primary-600 text-white rounded"
                        onClick={() => saveMeta(v)}
                        disabled={metaMutation.isPending}
                      >
                        Save
                      </button>
                      <button
                        className="px-2 py-1 text-xs border rounded"
                        onClick={() => setEditing(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {v.download_url && (
                      <button
                        className="text-xs text-primary-600 hover:underline"
                        onClick={() => handleDownload(v)}
                      >
                        Download
                      </button>
                    )}
                    {isArchitect && (
                      <>
                        {v.visibility !== 'archived' && (
                          <button
                            className="text-xs text-primary-600 hover:underline"
                            onClick={() => openEdit(v)}
                          >
                            Edit
                          </button>
                        )}
                        {!isCurrent && v.visibility !== 'archived' && (
                          <button
                            className="text-xs text-primary-600 hover:underline disabled:opacity-40"
                            disabled={busy}
                            onClick={() => restoreMutation.mutate(v.version_number)}
                          >
                            Restore as current
                          </button>
                        )}
                        {(v.visibility === 'internal' || v.visibility === 'review') && (
                          <button
                            className="text-xs text-green-700 hover:underline disabled:opacity-40"
                            disabled={busy}
                            onClick={() => issueMutation.mutate(v.version_number)}
                          >
                            Issue to client
                          </button>
                        )}
                        {v.visibility === 'internal' && (
                          <button
                            className="text-xs text-amber-700 hover:underline disabled:opacity-40"
                            disabled={busy}
                            onClick={() => reviewStateMutation.mutate({ v: v.version_number, inReview: true })}
                          >
                            Send to internal review
                          </button>
                        )}
                        {v.visibility === 'review' && (
                          <button
                            className="text-xs text-gray-600 hover:underline disabled:opacity-40"
                            disabled={busy}
                            onClick={() => reviewStateMutation.mutate({ v: v.version_number, inReview: false })}
                          >
                            Back to draft
                          </button>
                        )}
                        {(v.visibility === 'client_issued' || v.visibility === 'superseded') && (
                          <button
                            className="text-xs text-yellow-700 hover:underline disabled:opacity-40"
                            disabled={busy}
                            onClick={() => supersedeMutation.mutate(v.version_number)}
                          >
                            Mark superseded
                          </button>
                        )}
                        {v.visibility !== 'archived' && (
                          <button
                            className="text-xs text-gray-500 hover:underline disabled:opacity-40"
                            disabled={busy}
                            onClick={() => {
                              if (confirm('Archive this revision? It will be hidden from normal views.')) {
                                archiveMutation.mutate(v.version_number);
                              }
                            }}
                          >
                            Archive
                          </button>
                        )}
                        {versions && versions.length >= 2 && (
                          <button
                            className="text-xs text-indigo-700 hover:underline"
                            onClick={() => {
                              const other =
                                v.version_number === sorted[0]?.version_number
                                  ? sorted[1]
                                  : sorted[0];
                              if (other) onOpenCompare(v, other);
                            }}
                          >
                            Compare…
                          </button>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
