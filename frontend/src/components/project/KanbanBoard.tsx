import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { listMilestones } from '../../api/endpoints/milestones';
import { getProject } from '../../api/endpoints/projects';
import { updateFileMilestone } from '../../api/endpoints/files';
import useAuthStore from '../../stores/authStore';
import type { DesignFile, ProjectDetail } from '../../types';
import KanbanColumn from './KanbanColumn';
import { KanbanCardOverlay } from './KanbanCard';
import FileViewer from '../file/FileViewer';

interface KanbanBoardProps {
  projectId: number;
}

function groupFilesByMilestone(files: DesignFile[]): Map<number | null, DesignFile[]> {
  const groups = new Map<number | null, DesignFile[]>();
  for (const f of files) {
    const key = f.milestone_id;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(f);
  }
  return groups;
}

export default function KanbanBoard({ projectId }: KanbanBoardProps) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const isArchitect = user?.role === 'architect';
  const [error, setError] = useState<string | null>(null);
  const [viewingFile, setViewingFile] = useState<DesignFile | null>(null);
  const [activeFile, setActiveFile] = useState<DesignFile | null>(null);

  const mutation = useMutation({
    mutationFn: ({ fileId, milestoneId }: { fileId: string; milestoneId: number | null }) =>
      updateFileMilestone(fileId, { milestone_id: milestoneId }),
    onMutate: async ({ fileId, milestoneId }) => {
      await queryClient.cancelQueries({ queryKey: ['project', projectId] });
      const previous = queryClient.getQueryData<ProjectDetail>(['project', projectId]);
      queryClient.setQueryData<ProjectDetail>(['project', projectId], (old) => {
        if (!old) return old;
        return {
          ...old,
          files: old.files.map((f) => (f.id === fileId ? { ...f, milestone_id: milestoneId } : f)),
        };
      });
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(['project', projectId], ctx.previous);
      }
      setError('Failed to reassign file. Try again.');
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: milestones = [] } = useQuery({
    queryKey: ['milestones', projectId],
    queryFn: () => listMilestones(projectId),
  });

  const sortedMilestones = useMemo(
    () => [...milestones].sort((a, b) => a.position - b.position),
    [milestones],
  );

  const files = project?.files ?? [];

  const filesByMilestone = useMemo(() => groupFilesByMilestone(files), [files]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  function handleDragStart(event: DragStartEvent) {
    setActiveFile(event.active.data.current?.file ?? null);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveFile(null);
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const fileData = active.data.current?.file as DesignFile | undefined;
    if (!fileData) return;

    const targetMilestoneId = over.id === 'uncategorized' ? null : Number(over.id);
    const currentMilestoneId = fileData.milestone_id;

    if (targetMilestoneId === currentMilestoneId) return;

    setError(null);
    mutation.mutate({ fileId: fileData.id, milestoneId: targetMilestoneId });
  }

  async function handleFileClick(file: DesignFile) {
    setViewingFile(file);
  }

  if (milestones.length === 0) {
    return (
      <div className="border border-border bg-white py-12 px-6 text-center">
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
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
          />
        </svg>
        <p className="text-sm text-gray-500 max-w-xs mx-auto">
          Create milestones to use the board view
        </p>
      </div>
    );
  }

  return (
    <div>
      {error && (
        <div className="mb-3 px-4 py-2 bg-red-50 border border-red-200 text-sm text-red-700">
          {error}
        </div>
      )}

      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setActiveFile(null)}
      >
        <div className="flex gap-3 overflow-x-auto pb-3 -mx-1 px-1">
          {sortedMilestones.map((milestone) => (
            <KanbanColumn
              key={milestone.id}
              id={milestone.id}
              name={milestone.name}
              isCompleted={milestone.is_completed ?? false}
              files={filesByMilestone.get(milestone.id) ?? []}
              disabled={!isArchitect}
              onFileClick={handleFileClick}
            />
          ))}

          {filesByMilestone.has(null) && (
            <KanbanColumn
              key="uncategorized"
              id="uncategorized"
              name="Uncategorized"
              isCompleted={false}
              files={filesByMilestone.get(null) ?? []}
              disabled={!isArchitect}
              onFileClick={handleFileClick}
            />
          )}
        </div>
        <DragOverlay>{activeFile ? <KanbanCardOverlay file={activeFile} /> : null}</DragOverlay>
      </DndContext>

      {viewingFile && (
        <FileViewer file={viewingFile!} isOpen={true} onClose={() => setViewingFile(null)} />
      )}
    </div>
  );
}
