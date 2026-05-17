import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getProject } from '../api/endpoints/projects';
import { listProjectFiles } from '../api/endpoints/files';
import { listMilestones } from '../api/endpoints/milestones';
import useWebSocket from '../hooks/useWebSocket';
import FileList from '../components/file/FileList';
import MilestoneTimeline from '../components/milestone/MilestoneTimeline';
import Spinner from '../components/ui/Spinner';
import Button from '../components/ui/Button';

export default function ProjectView() {
  const { projectId } = useParams<{ projectId: string }>();
  const projectIdNum = Number(projectId);
  const { isConnected, isPolling } = useWebSocket(projectIdNum || null);

  const {
    data: project,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['project', projectIdNum],
    queryFn: () => getProject(projectIdNum),
    enabled: !!projectIdNum,
  });

  const {
    data: files,
    isLoading: filesLoading,
  } = useQuery({
    queryKey: ['files', projectIdNum],
    queryFn: () => listProjectFiles(projectIdNum),
    enabled: !!projectIdNum,
  });

  const {
    data: milestones,
    isLoading: milestonesLoading,
  } = useQuery({
    queryKey: ['milestones', projectIdNum],
    queryFn: () => listMilestones(projectIdNum),
    enabled: !!projectIdNum,
  });

  const [timelineOpen, setTimelineOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500 mb-4">Failed to load project</p>
        <Button variant="secondary" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const connectionColor = isConnected
    ? 'bg-green-500'
    : isPolling
      ? 'bg-yellow-500'
      : 'bg-red-500';
  const connectionLabel = isConnected ? 'Live' : isPolling ? 'Polling' : 'Offline';

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          {project.description && (
            <p className="text-gray-600 mt-1">{project.description}</p>
          )}
        </div>
        <div className="flex items-center space-x-2 text-sm">
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${connectionColor}`}
          />
          <span className="text-gray-500">{connectionLabel}</span>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="card text-center">
          <p className="text-2xl font-bold text-primary-600">{project.file_count}</p>
          <p className="text-sm text-gray-500">Files</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-primary-600">{project.milestone_count}</p>
          <p className="text-sm text-gray-500">Milestones</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-gray-600">
            {new Date(project.updated_at).toLocaleDateString()}
          </p>
          <p className="text-sm text-gray-500">Last Updated</p>
        </div>
      </div>

      {/* Milestone Timeline */}
      <div className="mb-8">
        <button
          onClick={() => setTimelineOpen((v) => !v)}
          className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4 w-full text-left"
        >
          <svg
            className={`w-4 h-4 transition-transform ${timelineOpen ? 'rotate-90' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Project Timeline
          <span className="text-sm font-normal text-gray-400 ml-2">
            {milestones?.length ?? 0} milestones
          </span>
        </button>
        {timelineOpen && (
          <>
            {milestonesLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="animate-pulse space-y-2">
                    <div className="h-5 bg-gray-200 rounded w-1/3" />
                    <div className="h-4 bg-gray-200 rounded w-full" />
                  </div>
                ))}
              </div>
            ) : !milestones || milestones.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <svg className="w-12 h-12 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
                <p className="text-sm text-gray-500 max-w-xs">
                  No milestones have been created for this project yet.
                </p>
              </div>
            ) : (
              <MilestoneTimeline
                milestones={milestones}
                isArchitect={false}
              />
            )}
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main area: File list */}
        <div className="lg:col-span-2 order-2 lg:order-1">
          {filesLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="card animate-pulse p-0 overflow-hidden">
                  <div className="aspect-square bg-gray-200" />
                  <div className="p-3 space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-3/4" />
                    <div className="h-3 bg-gray-200 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : files && files.length > 0 ? (
            <FileList files={files} projectId={projectIdNum} />
          ) : (
            <div className="card text-center py-12">
              <svg
                className="w-12 h-12 text-gray-300 mx-auto mb-4"
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
              <p className="text-gray-900 font-medium mb-1">
                No design files uploaded yet.
              </p>
              <p className="text-gray-500 text-sm">
                The architect will share files here.
              </p>
            </div>
          )}
        </div>

        {/* Side panel: Project info */}
        <div className="order-1 lg:order-2">
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Project Info
            </h2>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-gray-500">Architect</p>
                <p className="text-gray-900">
                  {project.files?.[0]?.uploaded_by?.name || '—'}
                </p>
              </div>
              <div>
                <p className="text-gray-500">Firm</p>
                <p className="text-gray-900">
                  {project.firm_id ? `Firm #${project.firm_id}` : '—'}
                </p>
              </div>
              <div>
                <p className="text-gray-500">Created</p>
                <p className="text-gray-900">
                  {new Date(project.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
