import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { compareVersions, getCompareJob } from '../../api/endpoints/files';
import Modal from '../ui/Modal';
import Icon from '../ui/icons';
import SegmentedControl from '../ui/SegmentedControl';
import Spinner from '../ui/Spinner';
import type { DesignFile, DiffPage, DiffRegionKind, FileVersion } from '../../types';

const SUPPORTED_IMAGES = new Set(['png', 'jpg', 'jpeg', 'webp']);

interface CompareModalProps {
  file: DesignFile;
  from: FileVersion;
  to: FileVersion;
  onClose: () => void;
}

function diffBadge(ratio: number) {
  if (ratio < 0.01)
    return { label: 'Unchanged', dot: 'bg-emerald-400', cls: 'bg-emerald-100 text-emerald-700' };
  if (ratio < 0.1)
    return { label: 'Minor', dot: 'bg-amber-400', cls: 'bg-amber-100 text-amber-700' };
  return { label: 'Significant', dot: 'bg-red-400', cls: 'bg-red-100 text-red-700' };
}

const REGION_COLORS: Record<DiffRegionKind, string> = {
  added: 'border-emerald-500 bg-emerald-400/25',
  removed: 'border-red-500 bg-red-400/25',
  modified: 'border-amber-500 bg-amber-400/25',
};

const pct = (value: number, total: number) => (total > 0 ? `${(value / total) * 100}%` : '0%');

function NoRender() {
  return (
    <div className="w-full aspect-[4/3] rounded border border-gray-200 bg-gray-50 flex items-center justify-center text-xs text-gray-400">
      No render requested
    </div>
  );
}

interface DiffViewProps {
  pages: DiffPage[];
  fromVersion: number;
  toVersion: number;
}

/** T4 Phase 2: page list + page-aligned side-by-side + change highlighting. */
function DiffView({ pages, fromVersion, toVersion }: DiffViewProps) {
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  const [showChanges, setShowChanges] = useState(true);
  const page = pages.find((p) => p.page_number === selectedPage) ?? pages[0];
  const badge = diffBadge(page.diff_ratio);

  return (
    <div className="flex gap-3">
      {/* Thumbnail-level page list with per-page diff indicator */}
      <div className="flex flex-col gap-1.5 w-44 shrink-0 max-h-[62vh] overflow-y-auto pr-1">
        {pages.map((p) => {
          const b = diffBadge(p.diff_ratio);
          const selected = p.page_number === page.page_number;
          return (
            <button
              key={p.page_number}
              onClick={() => setSelectedPage(p.page_number)}
              aria-pressed={selected}
              className={`flex items-center gap-2 rounded-lg border p-1.5 text-left transition-colors ${
                selected
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="relative w-12 h-12 shrink-0 rounded overflow-hidden border border-gray-200 bg-gray-100">
                <img
                  src={p.to_url ?? p.from_url ?? ''}
                  alt={`Page ${p.page_number} thumbnail`}
                  className="w-full h-full object-cover"
                />
                <span className={`absolute bottom-0 inset-x-0 h-1 ${b.dot}`} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-gray-800">Page {p.page_number}</p>
                <p
                  className={`text-[10px] font-semibold rounded px-1 py-0.5 inline-block ${b.cls}`}
                >
                  {b.label} · {Math.round(p.diff_ratio * 100)}%
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Page-aligned side-by-side with change highlighting */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium text-gray-500">
            Page {page.page_number} · {page.width} × {page.height} px
            <span className={`ml-2 rounded px-1.5 py-0.5 ${badge.cls}`}>
              {Math.round(page.diff_ratio * 100)}% changed
            </span>
          </p>
          <label className="flex items-center gap-1.5 text-xs font-medium text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={showChanges}
              onChange={(e) => setShowChanges(e.target.checked)}
              className="accent-primary-600"
            />
            Show changes
          </label>
        </div>
        <div className="overflow-auto max-h-[60vh] rounded-lg border border-gray-200">
          <div className="grid grid-cols-2 gap-3 p-3 min-w-[480px]">
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">v{fromVersion}</p>
              {page.from_url ? (
                <img
                  src={page.from_url}
                  alt={`v${fromVersion} page ${page.page_number}`}
                  className="w-full rounded border border-gray-100"
                />
              ) : (
                <NoRender />
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">v{toVersion}</p>
              <div className="relative">
                {page.to_url ? (
                  <img
                    src={page.to_url}
                    alt={`v${toVersion} page ${page.page_number}`}
                    className="w-full rounded border border-gray-100"
                  />
                ) : (
                  <NoRender />
                )}
                {showChanges &&
                  page.to_url &&
                  (page.overlay_url ? (
                    <img
                      src={page.overlay_url}
                      alt=""
                      aria-hidden="true"
                      className="absolute inset-0 w-full h-full pointer-events-none"
                    />
                  ) : (
                    page.regions.map((r, i) => (
                      <div
                        key={`${r.x}-${r.y}-${r.w}-${r.h}-${i}`}
                        className={`absolute border-2 pointer-events-none ${REGION_COLORS[r.kind]}`}
                        style={{
                          left: pct(r.x, page.width),
                          top: pct(r.y, page.height),
                          width: pct(r.w, page.width),
                          height: pct(r.h, page.height),
                        }}
                      />
                    ))
                  ))}
              </div>
            </div>
          </div>
        </div>
        {showChanges && !page.overlay_url && page.regions.length > 0 && (
          <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-600">
            {(['added', 'removed', 'modified'] as const).map((kind) => (
              <span key={kind} className="flex items-center gap-1 capitalize">
                <span
                  className={`inline-block w-3 h-3 rounded-sm border-2 ${REGION_COLORS[kind]}`}
                />
                {kind}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function CompareModal({ file, from, to, onClose }: CompareModalProps) {
  const [overlayOpacity, setOverlayOpacity] = useState(50);
  const [mode, setMode] = useState<'side' | 'overlay'>('side');
  const isImage = SUPPORTED_IMAGES.has(file.file_type);
  const isPdf = file.file_type === 'pdf';

  const { data, isLoading, isError } = useQuery({
    queryKey: ['compare', file.id, from.version_number, to.version_number],
    queryFn: () => compareVersions(file.id, from.version_number, to.version_number),
  });

  const jobId = data?.diff?.poll_url?.split('/').filter(Boolean).pop() || '';
  const { data: polled } = useQuery({
    queryKey: ['compare-poll', file.id, jobId],
    queryFn: () => getCompareJob(file.id, jobId),
    enabled: !!jobId && data?.diff?.status === 'pending',
    refetchInterval: (query) => (query.state.data?.diff?.status === 'pending' ? 2000 : false),
  });

  // While a diff job is pending the polled response replaces the initial one.
  const live = polled ?? data;
  const pages = live?.diff?.pages ?? [];
  const diffReady = live?.diff?.status === 'ready' && pages.length > 0;
  const diffPending = live?.diff?.status === 'pending';

  const result = live;
  const fromUrl = result?.from?.download_url;
  const toUrl = result?.to?.download_url;

  return (
    <Modal
      isOpen
      onClose={onClose}
      size="lg"
      title={`Compare v${from.version_number} → v${to.version_number}`}
    >
      <div className="space-y-4">
        {/* Revision metadata beside the comparison (T4) */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg border border-gray-100 p-3">
            <p className="font-semibold text-gray-900 mb-1">v{from.version_number}</p>
            {from.name && (
              <p className="text-gray-700 flex items-center gap-1">
                <Icon name="pin" className="w-3.5 h-3.5" /> {from.name}
              </p>
            )}
            {from.revision_message && (
              <p className="italic text-gray-600">"{from.revision_message}"</p>
            )}
            <p className="text-gray-400 mt-1">{new Date(from.created_at).toLocaleString()}</p>
            {from.uploaded_by && <p className="text-gray-400">by {from.uploaded_by.name}</p>}
          </div>
          <div className="rounded-lg border border-gray-100 p-3">
            <p className="font-semibold text-gray-900 mb-1">v{to.version_number}</p>
            {to.name && (
              <p className="text-gray-700 flex items-center gap-1">
                <Icon name="pin" className="w-3.5 h-3.5" /> {to.name}
              </p>
            )}
            {to.revision_message && <p className="italic text-gray-600">"{to.revision_message}"</p>}
            <p className="text-gray-400 mt-1">{new Date(to.created_at).toLocaleString()}</p>
            {to.uploaded_by && <p className="text-gray-400">by {to.uploaded_by.name}</p>}
          </div>
        </div>

        {isLoading && (
          <div className="flex justify-center py-12">
            <Spinner size="lg" />
          </div>
        )}

        {!isLoading && result && !result.supported && (
          <div className="flex flex-col items-center gap-3 py-10 text-center text-gray-500">
            <svg
              className="w-12 h-12 text-gray-300"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-sm max-w-sm">{result.explanation}</p>
            {from.download_url && to.download_url && (
              <div className="flex gap-3">
                <a
                  href={from.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-600 underline text-sm"
                >
                  Download v{from.version_number}
                </a>
                <a
                  href={to.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-600 underline text-sm"
                >
                  Download v{to.version_number}
                </a>
              </div>
            )}
          </div>
        )}

        {!isLoading && result && diffPending && (
          <div className="flex flex-col items-center gap-3 py-10 text-center text-gray-500">
            <Spinner size="lg" />
            <p className="text-sm">Computing diff…</p>
            <p className="text-xs text-gray-400">Large PDFs can take a moment.</p>
          </div>
        )}

        {!isLoading && result && diffReady && (
          <DiffView pages={pages} fromVersion={from.version_number} toVersion={to.version_number} />
        )}

        {!isLoading && result?.supported && !diffPending && !diffReady && (
          <>
            {(isImage || isPdf) && (
              <div className="flex items-center gap-2 flex-wrap">
                <SegmentedControl
                  ariaLabel="Comparison mode"
                  size="sm"
                  options={[
                    { value: 'side', label: 'Side by side' },
                    ...(isImage ? [{ value: 'overlay' as const, label: 'Overlay' }] : []),
                  ]}
                  value={mode}
                  onChange={(v) => setMode(v)}
                />
                {isImage && mode === 'overlay' && (
                  <label className="flex items-center gap-2 text-xs text-gray-600">
                    Opacity
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={overlayOpacity}
                      onChange={(e) => setOverlayOpacity(Number(e.target.value))}
                      className="w-32"
                    />
                    <span>{overlayOpacity}%</span>
                  </label>
                )}
              </div>
            )}

            {mode === 'side' && (isImage || isPdf) && fromUrl && toUrl && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-1">v{from.version_number}</p>
                  {isImage ? (
                    <img
                      src={fromUrl}
                      alt={`v${from.version_number}`}
                      className="w-full rounded border border-gray-200"
                    />
                  ) : (
                    <iframe
                      src={fromUrl}
                      title={`v${from.version_number}`}
                      className="w-full h-96 border border-gray-200 rounded"
                    />
                  )}
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-1">v{to.version_number}</p>
                  {isImage ? (
                    <img
                      src={toUrl}
                      alt={`v${to.version_number}`}
                      className="w-full rounded border border-gray-200"
                    />
                  ) : (
                    <iframe
                      src={toUrl}
                      title={`v${to.version_number}`}
                      className="w-full h-96 border border-gray-200 rounded"
                    />
                  )}
                </div>
              </div>
            )}

            {mode === 'overlay' && isImage && fromUrl && toUrl && (
              <div className="relative rounded border border-gray-200 overflow-hidden">
                <img src={fromUrl} alt={`v${from.version_number}`} className="w-full" />
                <img
                  src={toUrl}
                  alt={`v${to.version_number}`}
                  className="absolute inset-0 w-full"
                  style={{ opacity: overlayOpacity / 100 }}
                />
                <div className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                  Newer revision {overlayOpacity}% visible
                </div>
              </div>
            )}
          </>
        )}

        {!isLoading && isError && (
          <p className="text-sm text-red-600 text-center py-8">Failed to load comparison.</p>
        )}
      </div>
    </Modal>
  );
}
