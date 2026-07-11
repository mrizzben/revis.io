import { useDroppable } from '@dnd-kit/core';
import type { DesignFile } from '../../types';
import KanbanCard from './KanbanCard';

interface KanbanColumnProps {
  id: number | string;
  name: string;
  isCompleted: boolean;
  files: DesignFile[];
  disabled?: boolean;
  onFileClick?: (file: DesignFile) => void;
}

export default function KanbanColumn({ id, name, isCompleted, files, disabled, onFileClick }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id, disabled });

  return (
    <div
      ref={setNodeRef}
      className={`flex flex-col min-w-[220px] max-w-[260px] w-full shrink-0 border transition-colors ${
        isOver ? 'bg-primary-50 border-primary-500' : 'bg-surface-secondary border-border'
      }`}
    >
      <div className={`flex items-center justify-between px-3 py-2.5 border-b ${
        isCompleted ? 'bg-green-50 border-green-200' : 'bg-white border-border'
      }`}>
        <h3 className="text-sm font-semibold text-gray-700 truncate max-w-[140px]" title={name}>
          {name}
        </h3>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-400 font-medium">{files.length}</span>
          {isCompleted && (
            <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
      </div>

      <div className="flex-1 p-2 space-y-2 overflow-y-auto max-h-[calc(100vh-280px)]">
        {files.length === 0 ? (
          <div className="flex items-center justify-center h-20 text-xs text-gray-400 text-center px-2">
            No files in this milestone
          </div>
        ) : (
          files.map((file) => (
            <KanbanCard
              key={file.id}
              file={file}
              disabled={disabled}
              onClick={() => onFileClick?.(file)}
            />
          ))
        )}
      </div>
    </div>
  );
}