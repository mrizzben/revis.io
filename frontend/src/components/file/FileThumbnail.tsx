import { getThumbnailUrl, uploadComplete } from '../../api/endpoints/files';
import { DesignFile, ThumbnailStatus } from '../../types';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Spinner from '../ui/Spinner';

interface FileThumbnailProps {
  file: DesignFile;
  size?: 'small' | 'medium';
}

const sizeClasses: Record<'small' | 'medium', string> = {
  small: 'w-[200px] h-[200px]',
  medium: 'w-[600px] h-[600px]',
};

function FilePlaceholder({ type, className = '' }: { type: string; className?: string }) {
  const isPdf = type === 'pdf';
  const is3D = new Set(['ifc', 'obj', 'stl', 'glb', 'gltf']).has(type);

  if (isPdf) {
    return (
      <svg className={`w-12 h-12 text-red-300 ${className}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    );
  }

  if (is3D) {
    return (
      <svg className={`w-12 h-12 text-orange-300 ${className}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
      </svg>
    );
  }

  return (
    <svg className={`w-12 h-12 text-gray-300 ${className}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

export default function FileThumbnail({ file, size = 'small' }: FileThumbnailProps) {
  const queryClient = useQueryClient();
  const status: ThumbnailStatus = file.thumbnail_status;

  const { data: thumbnailUrl, isLoading, isError } = useQuery({
    queryKey: ['thumbnail', file.id, size],
    queryFn: () => getThumbnailUrl(file.id, size),
    enabled: status === 'complete',
    staleTime: 30 * 60 * 1000,
    retry: false,
  });

  const handleRetry = () => {
    uploadComplete(file.id).then(() => {
      queryClient.invalidateQueries({ queryKey: ['thumbnail', file.id] });
    });
  };

  const placeholderBase = `w-full h-full bg-gray-100 flex flex-col items-center justify-center gap-2 ${sizeClasses[size]}`;

  if (status === 'complete' && thumbnailUrl) {
    return (
      <div className={sizeClasses[size]}>
        <img
          src={thumbnailUrl}
          alt={file.filename}
          className="w-full h-full object-cover"
        />
      </div>
    );
  }

  if (status === 'pending') {
    return (
      <div className={placeholderBase}>
        <FilePlaceholder type={file.file_type} className="animate-pulse" />
        <span className="text-xs text-gray-400">Pending</span>
      </div>
    );
  }

  if (status === 'processing') {
    return (
      <div className={placeholderBase}>
        <FilePlaceholder type={file.file_type} />
        <Spinner size="sm" />
        <span className="text-xs text-gray-400">Processing...</span>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className={placeholderBase}>
        <FilePlaceholder type={file.file_type} className="text-red-300" />
        <span className="text-xs text-red-500">Thumbnail failed</span>
        <button
          onClick={handleRetry}
          className="text-xs text-primary-600 hover:text-primary-700 underline mt-1"
        >
          Retry
        </button>
      </div>
    );
  }

  if (status === 'unsupported') {
    return (
      <div className={`${placeholderBase} group relative`}>
        <FilePlaceholder type={file.file_type} />
        <span className="text-xs text-gray-400">No preview</span>
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 bg-black/60 transition-opacity">
          <span className="text-white text-xs">No preview available</span>
        </div>
      </div>
    );
  }

  if (isLoading && status === 'complete') {
    return (
      <div className={placeholderBase}>
        <Spinner size="md" />
        <span className="text-xs text-gray-400">Loading thumbnail...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className={placeholderBase}>
        <FilePlaceholder type={file.file_type} className="text-yellow-300" />
        <span className="text-xs text-gray-400">Thumbnail unavailable</span>
      </div>
    );
  }

  return (
    <div className={placeholderBase}>
      <FilePlaceholder type={file.file_type} />
      <span className="text-xs text-gray-400">{file.file_type.toUpperCase()}</span>
    </div>
  );
}