import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as projectsApi from '../api/endpoints/projects';
import {
  listMilestones,
  createMilestone,
  updateMilestone,
  deleteMilestone,
} from '../api/endpoints/milestones';
import MilestoneTimeline from '../components/milestone/MilestoneTimeline';
import MilestoneForm from '../components/milestone/MilestoneForm';
import KanbanBoard from '../components/project/KanbanBoard';
import useWebSocket from '../hooks/useWebSocket';
import Button from '../components/ui/Button';
import FileUploader from '../components/file/FileUploader';
import FileList from '../components/file/FileList';
import InviteForm from '../components/project/InviteForm';
import Skeleton from '../components/ui/Skeleton';
import OptionsPanel from '../components/options/OptionsPanel';
import ActivityTimeline from '../components/activity/ActivityTimeline';
import { listCollaborators } from '../api/endpoints/collaborators';
import type { Milestone } from '../types';

export default function ProjectManage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projectIdNum = Number(projectId);
  useWebSocket(projectIdNum || null);

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectIdNum],
    queryFn: () => projectsApi.getProject(projectIdNum),
    enabled: !!projectIdNum,
  });

  const { data: milestones = [] } = useQuery({
    queryKey: ['milestones', projectIdNum],
    queryFn: () => listMilestones(projectIdNum),
    enabled: !!projectIdNum,
  });

  const { data: collaborators = [] } = useQuery({
    queryKey: ['collaborators', projectIdNum],
    queryFn: async () => {
      const resp = await listCollaborators(projectIdNum);
      const owner = resp.owner ? [{ id: resp.owner.user_id, name: resp.owner.name }] : [];
      return [...owner, ...resp.collaborators.map((c) => ({ id: c.user_id, name: c.name }))];
    },
    enabled: !!projectIdNum,
  });

  const [showMilestoneForm, setShowMilestoneForm] = useState(false);
  const [editingMilestone, setEditingMilestone] = useState<Milestone | null>(null);
  const [milestoneFormLoading, setMilestoneFormLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'timeline' | 'board'>('timeline');

  const handleUploadSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['project', projectIdNum] });
  };

  const handleOpenCreateMilestone = () => {
    setEditingMilestone(null);
    setShowMilestoneForm(true);
  };

  const handleOpenEditMilestone = (milestone: Milestone) => {
    setEditingMilestone(milestone);
    setShowMilestoneForm(true);
  };

  const handleCloseMilestoneForm = () => {
    setShowMilestoneForm(false);
    setEditingMilestone(null);
  };

  const handleMilestoneSubmit = async (data: {
    name: string;
    description?: string;
    position?: number;
  }) => {
    setMilestoneFormLoading(true);
    try {
      if (editingMilestone) {
        await updateMilestone(editingMilestone.id, data);
      } else {
        await createMilestone(projectIdNum, data);
      }
      queryClient.invalidateQueries({ queryKey: ['milestones', projectIdNum] });
      queryClient.invalidateQueries({ queryKey: ['project', projectIdNum] });
      handleCloseMilestoneForm();
    } finally {
      setMilestoneFormLoading(false);
    }
  };

  const handleDeleteMilestone = async (id: number) => {
    await deleteMilestone(id);
    queryClient.invalidateQueries({ queryKey: ['milestones', projectIdNum] });
    queryClient.invalidateQueries({ queryKey: ['project', projectIdNum] });
  };

  if (isLoading) {
    return (
      <div>
        <div className="mb-6">
          <Skeleton height="24px" width="100px" className="mb-2" />
          <Skeleton height="32px" width="280px" className="mb-2" />
          <Skeleton height="16px" width="200px" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
          <Skeleton height="80px" className="rounded-xl" count={3} />
        </div>
        <div className="card mb-8 space-y-4">
          <div className="flex justify-between">
            <Skeleton height="24px" width="100px" />
            <Skeleton height="40px" width="120px" className="rounded-lg" />
          </div>
          <Skeleton height="16px" className="mb-2" count={4} />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="card">
              <Skeleton height="24px" width="160px" className="mb-4" />
              <Skeleton height="160px" className="rounded-xl" />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="card p-0 overflow-hidden">
                  <Skeleton height="0" className="aspect-square" />
                  <div className="p-3 space-y-2">
                    <Skeleton height="14px" width="75%" />
                    <Skeleton height="14px" width="50%" />
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="card space-y-4">
              <Skeleton height="24px" width="120px" />
              <Skeleton height="40px" className="rounded-lg" />
              <Skeleton height="40px" className="rounded-lg" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500">Project not found</p>
        <Button className="mt-4" variant="secondary" onClick={() => navigate('/dashboard')}>
          Back to Dashboard
        </Button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate('/dashboard')}
            className="text-sm text-gray-500 hover:text-gray-700 mb-1"
          >
            ← Dashboard
          </button>
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          {project.description && <p className="text-gray-600 mt-1">{project.description}</p>}
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
        <div className="card text-center">
          <p className="text-2xl font-bold text-primary-600">{project.file_count}</p>
          <p className="text-sm text-gray-500">Files</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-primary-600">{project.milestone_count}</p>
          <p className="text-sm text-gray-500">Milestones</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-green-600">{project.completed_milestone_count}</p>
          <p className="text-sm text-gray-500">Completed</p>
        </div>
      </div>

      {/* Milestones */}
      <div className="card mb-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">Milestones</h2>
            <div className="flex rounded-lg border border-gray-200 overflow-hidden">
              <button
                onClick={() => setViewMode('timeline')}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  viewMode === 'timeline'
                    ? 'bg-primary-500 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                Timeline
              </button>
              <button
                onClick={() => setViewMode('board')}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  viewMode === 'board'
                    ? 'bg-primary-500 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                Board
              </button>
            </div>
          </div>
          <Button onClick={handleOpenCreateMilestone}>Add Milestone</Button>
        </div>

        {viewMode === 'timeline' ? (
          <MilestoneTimeline
            milestones={milestones}
            isArchitect
            projectId={projectIdNum}
            onEdit={handleOpenEditMilestone}
            onDelete={handleDeleteMilestone}
          />
        ) : (
          <KanbanBoard projectId={projectIdNum} />
        )}
      </div>

      <MilestoneForm
        isOpen={showMilestoneForm}
        onClose={handleCloseMilestoneForm}
        onSubmit={handleMilestoneSubmit}
        initialData={
          editingMilestone
            ? {
                name: editingMilestone.name,
                description: editingMilestone.description ?? undefined,
                position: editingMilestone.position,
              }
            : undefined
        }
        isLoading={milestoneFormLoading}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* File upload + list */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Upload Design Files</h2>
            <FileUploader projectId={projectIdNum} onUploadSuccess={handleUploadSuccess} />
          </div>

          <div>
            <FileList
              files={project.files}
              onFileDeleted={handleUploadSuccess}
              projectId={projectIdNum}
              milestones={milestones}
              collaborators={collaborators}
            />
          </div>

          {/* Design options (T5) */}
          <OptionsPanel projectId={projectIdNum} isOwner files={project.files ?? []} />
        </div>

        {/* Sidebar: Invite + Activity */}
        <div className="space-y-6">
          <InviteForm projectId={projectIdNum} />
          <ActivityTimeline projectId={projectIdNum} />
        </div>
      </div>
    </div>
  );
}
