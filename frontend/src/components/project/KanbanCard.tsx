import type { DesignFile } from '../../types';
import { useDraggable } from '@dnd-kit/core';
import FileThumbnail from '../file/FileThumbnail';
import Badge from '../ui/Badge';

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

/** Presentational card body shared by the static card and the drag overlay. */
function CardBody({ file, className = '' }: { file: DesignFile; className?: string }) {
  return (
    <div className={`border border-border bg-white ${className}`}>
      <div className="aspect-square bg-gray-100 relative border-b border-border overflow-hidden">
        <FileThumbnail file={file} size="small" />
      </div>
      <div className="p-2.5">
        <p className="text-sm font-medium text-gray-900 truncate" title={file.filename}>
          {file.filename}
        </p>
        <div className="flex items-center justify-between mt-1">
          <Badge className={FILE_TYPE_COLORS[file.file_type] || 'bg-gray-100 text-gray-700'}>
            {file.file_type.toUpperCase()}
          </Badge>
          <span className="text-xs text-gray-400">v{file.version_number}</span>
        </div>
      </div>
    </div>
  );
}

/** Card rendered inside the drag overlay, tracking the cursor. */
export function KanbanCardOverlay({ file }: { file: DesignFile }) {
  return (
    <div className="w-[240px] rotate-3 shadow-lg shadow-gray-400/40 select-none pointer-events-none">
      <CardBody file={file} className="ring-2 ring-primary-500" />
    </div>
  );
}

interface KanbanCardProps {
  file: DesignFile;
  disabled?: boolean;
  onClick?: () => void;
}

export default function KanbanCard({ file, disabled = false, onClick }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: file.id,
    data: { file, milestoneId: file.milestone_id },
    disabled,
  });

  return (
    <div
      ref={disabled ? undefined : setNodeRef}
      {...(disabled ? {} : listeners)}
      {...(disabled ? {} : attributes)}
      onClick={onClick}
      className={`group ${
        disabled
          ? ''
          : isDragging
            ? 'opacity-30 cursor-grabbing'
            : 'cursor-grab active:cursor-grabbing'
      }`}
    >
      <CardBody file={file} className="transition-colors hover:bg-gray-50" />
    </div>
  );
}
