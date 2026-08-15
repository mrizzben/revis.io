import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { compareVersions } from '../../api/endpoints/files';
import Modal from '../ui/Modal';
import Spinner from '../ui/Spinner';
import type { DesignFile, FileVersion } from '../../types';

const SUPPORTED_IMAGES = new Set(['png', 'jpg', 'jpeg', 'webp']);

interface CompareModalProps {
  file: DesignFile;
  from: FileVersion;
  to: FileVersion;
  onClose: () => void;
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

  const result = data;
  const fromUrl = result?.from?.download_url;
  const toUrl = result?.to?.download_url;

  return (
    <Modal isOpen onClose={onClose} size="lg" title={`Compare v${from.version_number} → v${to.version_number}`}>
      <div className="space-y-4">
        {/* Revision metadata beside the comparison (T4) */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg border border-gray-100 p-3">
            <p className="font-semibold text-gray-900 mb-1">v{from.version_number}</p>
            {from.name && <p className="text-gray-700">📌 {from.name}</p>}
            {from.revision_message && <p className="italic text-gray-600">"{from.revision_message}"</p>}
            <p className="text-gray-400 mt-1">{new Date(from.created_at).toLocaleString()}</p>
            {from.uploaded_by && <p className="text-gray-400">by {from.uploaded_by.name}</p>}
          </div>
          <div className="rounded-lg border border-gray-100 p-3">
            <p className="font-semibold text-gray-900 mb-1">v{to.version_number}</p>
            {to.name && <p className="text-gray-700">📌 {to.name}</p>}
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
            <svg className="w-12 h-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm max-w-sm">{result.explanation}</p>
            {from.download_url && to.download_url && (
              <div className="flex gap-3">
                <a href={from.download_url} target="_blank" rel="noopener noreferrer" className="text-primary-600 underline text-sm">
                  Download v{from.version_number}
                </a>
                <a href={to.download_url} target="_blank" rel="noopener noreferrer" className="text-primary-600 underline text-sm">
                  Download v{to.version_number}
                </a>
              </div>
            )}
          </div>
        )}

        {!isLoading && result?.supported && (
          <>
            {(isImage || isPdf) && (
              <div className="flex items-center gap-2">
                <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                  <button
                    onClick={() => setMode('side')}
                    className={`px-3 py-1.5 text-xs font-medium ${mode === 'side' ? 'bg-primary-500 text-white' : 'bg-white text-gray-600'}`}
                  >
                    Side by side
                  </button>
                  {isImage && (
                    <button
                      onClick={() => setMode('overlay')}
                      className={`px-3 py-1.5 text-xs font-medium ${mode === 'overlay' ? 'bg-primary-500 text-white' : 'bg-white text-gray-600'}`}
                    >
                      Overlay
                    </button>
                  )}
                </div>
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
                    <img src={fromUrl} alt={`v${from.version_number}`} className="w-full rounded border border-gray-200" />
                  ) : (
                    <iframe src={fromUrl} title={`v${from.version_number}`} className="w-full h-96 border border-gray-200 rounded" />
                  )}
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-1">v{to.version_number}</p>
                  {isImage ? (
                    <img src={toUrl} alt={`v${to.version_number}`} className="w-full rounded border border-gray-200" />
                  ) : (
                    <iframe src={toUrl} title={`v${to.version_number}`} className="w-full h-96 border border-gray-200 rounded" />
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
