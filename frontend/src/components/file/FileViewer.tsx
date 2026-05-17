import { useEffect, useState } from 'react';
import { getDownloadUrl } from '../../api/endpoints/files';
import { DesignFile } from '../../types';
import Modal from '../ui/Modal';
import Badge from '../ui/Badge';
import Spinner from '../ui/Spinner';
import CommentThread from '../comment/CommentThread';
import useAuthStore from '../../stores/authStore';

interface FileViewerProps {
  file: DesignFile;
  isOpen: boolean;
  onClose: () => void;
}

const SUPPORTED_IMAGES = new Set(['png', 'jpg', 'jpeg', 'webp']);
const SUPPORTED_3D = new Set(['ifc', 'obj', 'stl', 'glb', 'gltf']);

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const val = bytes / Math.pow(1024, i);
  return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function FileTypeIcon({ type, className = '' }: { type: string; className?: string }) {
  if (SUPPORTED_IMAGES.has(type)) {
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    );
  }
  if (type === 'pdf') {
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    );
  }
  if (SUPPORTED_3D.has(type)) {
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
      </svg>
    );
  }
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

export default function FileViewer({ file, isOpen, onClose }: FileViewerProps) {
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showComments, setShowComments] = useState(false);

  const user = useAuthStore((state) => state.user);
  const currentUserId = user?.id || 0;
  const isArchitect = user?.role === 'architect';

  useEffect(() => {
    if (!isOpen) return;
    setDownloadUrl(null);
    setError(null);
    setLoading(true);

    getDownloadUrl(file.id)
      .then(({ url }) => {
        setDownloadUrl(url);
        setLoading(false);
      })
      .catch(() => {
        setError('Failed to load file preview');
        setLoading(false);
      });
  }, [file.id, isOpen]);

  const handleDownload = () => {
    if (downloadUrl) {
      window.open(downloadUrl, '_blank');
    }
  };

  const isImage = SUPPORTED_IMAGES.has(file.file_type);
  const isPdf = file.file_type === 'pdf';
  const is3D = SUPPORTED_3D.has(file.file_type);

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg" title={file.filename} fullScreenMobile>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <Badge variant="info">{file.file_type.toUpperCase()}</Badge>
          <span>{formatBytes(file.file_size)}</span>
        </div>

        <div className="flex items-center justify-center min-h-[300px] max-h-[70vh] overflow-auto bg-gray-50 rounded-lg">
          {loading && (
            <div className="flex flex-col items-center gap-3">
              <Spinner size="lg" />
              <p className="text-sm text-gray-400">Loading preview...</p>
            </div>
          )}

          {!loading && error && (
            <div className="flex flex-col items-center gap-3 text-gray-400">
              <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm">{error}</p>
            </div>
          )}

          {!loading && !error && isImage && downloadUrl && (
            <img
              src={downloadUrl}
              alt={file.filename}
              className="max-w-full max-h-[70vh] object-contain"
            />
          )}

          {!loading && !error && isPdf && downloadUrl && (
            <iframe
              src={downloadUrl}
              title={file.filename}
              className="w-full h-[70vh] border-0"
            />
          )}

          {!loading && !error && is3D && (
            <div className="flex flex-col items-center gap-3 text-gray-400 p-8">
              <FileTypeIcon type={file.file_type} className="w-16 h-16 text-gray-300" />
              <p className="text-sm text-center">
                3D preview available for supported formats
              </p>
              {downloadUrl && (
                <a
                  href={downloadUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-600 hover:text-primary-700 text-sm font-medium underline"
                >
                  Download to view in your 3D application
                </a>
              )}
            </div>
          )}

          {!loading && !error && !isImage && !isPdf && !is3D && (
            <div className="flex flex-col items-center gap-3 text-gray-400 p-8">
              <FileTypeIcon type={file.file_type} className="w-16 h-16 text-gray-300" />
              <p className="text-sm font-medium text-gray-600">{file.filename}</p>
              <p className="text-xs">{formatBytes(file.file_size)}</p>
              {downloadUrl && (
                <a
                  href={downloadUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 mt-2 px-3 py-1.5 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download
                </a>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
          <button
            onClick={handleDownload}
            disabled={!downloadUrl}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download
          </button>
        </div>

        <div className="border-t border-gray-200 pt-3">
          <button
            onClick={() => setShowComments(!showComments)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 w-full"
          >
            <span>Comments ({file.comment_count ?? 0})</span>
            <svg
              className={`w-4 h-4 transition-transform ${showComments ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {showComments && (
            <div className="mt-3">
              <CommentThread
                fileId={file.id}
                projectId={file.project_id}
                currentUserId={currentUserId}
                isArchitect={isArchitect}
              />
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}