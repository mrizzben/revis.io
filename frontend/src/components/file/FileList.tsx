import { useState, useMemo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as filesApi from '../../api/endpoints/files';
import Badge from '../ui/Badge';
import FileThumbnail from './FileThumbnail';
import FileViewer from './FileViewer';
import type { DesignFile } from '../../types';

interface Milestone {
  id: number;
  name: string;
}

interface CollaboratorBrief {
  id: number;
  name: string;
}

interface FileListProps {
  files?: DesignFile[];
  projectId: number;
  onFileDeleted?: () => void;
  milestoneId?: number;
  milestones?: Milestone[];
  collaborators?: CollaboratorBrief[];
  selectedMilestoneId?: number | null;
  onMilestoneFilterChange?: (milestoneId: number | null) => void;
}

const FILE_TYPE_COLORS: Record<string, string> = {
  png: 'bg-green-100 text-green-700',
  jpg: 'bg-green-100 text-green-700',
  jpeg: 'bg-green-100 text-green-700',
  webp: 'bg-green-100 text-green-700',
  pdf: 'bg-red-100 text-red-700',
  dwg: 'bg-blue-100 text-blue-700',
  dxf: 'bg-blue-100 text-blue-700',
  skp: 'bg-purple-100 text-purple-700',
  rvt: 'bg-purple-100 text-purple-700',
  ifc: 'bg-orange-100 text-orange-700',
  obj: 'bg-orange-100 text-orange-700',
  stl: 'bg-orange-100 text-orange-700',
};

export default function FileList({
  files,
  projectId,
  onFileDeleted,
  milestones,
  collaborators,
  selectedMilestoneId,
  onMilestoneFilterChange,
}: FileListProps) {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<DesignFile | null>(null);

  const milestoneMap = useMemo(() => {
    if (!milestones) return new Map<number, string>();
    return new Map(milestones.map((m) => [m.id, m.name]));
  }, [milestones]);

  const filteredFiles = useMemo(() => {
    if (!files) return [];
    if (selectedMilestoneId != null) {
      return files.filter((f) => f.milestone_id === selectedMilestoneId);
    }
    return files;
  }, [files, selectedMilestoneId]);

  const groupedFiles = useMemo(() => {
    if (!files || !milestones || selectedMilestoneId != null) return null;
    const groups = new Map<number | null, DesignFile[]>();
    for (const f of files) {
      const key = f.milestone_id;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(f);
    }
    const sortedGroups = Array.from(groups.entries()).sort(([a], [b]) => {
      if (a == null) return -1;
      if (b == null) return 1;
      return 0;
    });
    return sortedGroups;
  }, [files, milestones, selectedMilestoneId]);

  const deleteMutation = useMutation({
    mutationFn: (fileId: string) => filesApi.deleteFile(fileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      onFileDeleted?.();
    },
  });

  const handleViewFile = async (file: DesignFile) => {
    setSelectedFile(file);
  };

  if (!files || files.length === 0) {
    return (
      <div className="border border-border bg-white py-8 text-center">
        <svg
          className="w-10 h-10 text-gray-300 mx-auto mb-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
          />
        </svg>
        <p className="text-gray-500 text-sm">No files uploaded yet</p>
        <p className="text-gray-400 text-xs mt-1">
          Upload your first design file using the upload area above
        </p>
      </div>
    );
  }

  const renderFileCard = (file: DesignFile) => (
    <div
      key={file.id}
      className="border border-border bg-white hover:border-primary-300 transition-colors cursor-pointer group"
      onClick={() => handleViewFile(file)}
    >
      <div className="aspect-square bg-gray-100 relative border-b border-border">
        <FileThumbnail file={file} size="medium" />
      </div>
      <div className="p-3">
        <p className="text-sm font-medium text-gray-900 truncate" title={file.filename}>
          {file.filename}
        </p>
        <div className="flex items-center justify-between mt-1">
          <Badge className={FILE_TYPE_COLORS[file.file_type] || 'bg-gray-100 text-gray-700'}>
            {file.file_type.toUpperCase()}
          </Badge>
          <span className="text-xs text-gray-400">
            {(file.file_size / (1024 * 1024)).toFixed(1)} MB
          </span>
        </div>
        {file.comment_count != null && file.comment_count > 0 && (
          <div className="mt-1">
            <span className="inline-flex items-center gap-1 text-xs text-gray-500">
              💬 {file.comment_count}
            </span>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1 mt-1">
          {file.milestone_id != null && milestoneMap.has(file.milestone_id) && (
            <Badge className="bg-indigo-100 text-indigo-700 text-xs">
              {milestoneMap.get(file.milestone_id)}
            </Badge>
          )}
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-400">
            {new Date(file.created_at).toLocaleDateString()}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (confirm('Delete this file?')) deleteMutation.mutate(file.id);
            }}
            className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {milestones && milestones.length > 0 && (
        <div className="flex items-center mb-4 gap-2">
          <label className="text-sm text-gray-600 font-medium">Filter:</label>
          <select
            className="border border-border px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-primary-500"
            value={selectedMilestoneId ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              onMilestoneFilterChange?.(val ? Number(val) : null);
            }}
          >
            <option value="">All Files</option>
            {milestones.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {groupedFiles ? (
        groupedFiles.map(([milestoneId, groupFiles]) => (
          <div key={milestoneId ?? 'uncategorized'} className="mb-6">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              {milestoneId != null && milestoneMap.has(milestoneId)
                ? milestoneMap.get(milestoneId)
                : 'Uncategorized'}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {groupFiles.map(renderFileCard)}
            </div>
          </div>
        ))
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filteredFiles.map(renderFileCard)}
        </div>
      )}

      {selectedFile && (
        <FileViewer
          file={selectedFile}
          isOpen={true}
          onClose={() => setSelectedFile(null)}
          milestones={milestones}
          collaborators={collaborators}
        />
      )}
    </>
  );
}
