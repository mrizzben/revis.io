import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import useAuthStore from '../stores/authStore';
import useWebSocket from '../hooks/useWebSocket';
import * as projectsApi from '../api/endpoints/projects';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Modal from '../components/ui/Modal';
import Skeleton from '../components/ui/Skeleton';
import ProjectCard from '../components/project/ProjectCard';
import type { CreateProjectRequest } from '../types';

export default function Dashboard() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');

  const { isConnected } = useWebSocket(null);

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.listProjects(),
    refetchInterval: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateProjectRequest) => projectsApi.createProject(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setIsCreateOpen(false);
      setNewProjectName('');
      setNewProjectDesc('');
    },
  });

  const handleCreateProject = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({ name: newProjectName, description: newProjectDesc || undefined });
  };

  const createError = createMutation.isError
    ? (() => {
        const err = createMutation.error as { response?: { data?: { detail?: unknown } } };
        const detail = err?.response?.data?.detail;
        return typeof detail === 'string' ? detail : 'Failed to create project. Please try again.';
      })()
    : null;

  const stats = {
    total: projects?.length || 0,
    active: projects?.filter((p) => !p.is_archived).length || 0,
    totalFiles: projects?.reduce((sum, p) => sum + p.file_count, 0) || 0,
  };

  if (isLoading) {
    return (
      <div>
        <div className="flex items-center justify-between mb-8">
          <div>
            <Skeleton height="28px" width="200px" className="mb-2" />
            <Skeleton height="16px" width="160px" />
          </div>
          <Skeleton height="40px" width="120px" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
          <Skeleton height="80px" count={3} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="border border-border bg-white">
              <Skeleton height="120px" />
              <div className="p-4 space-y-3">
                <Skeleton height="20px" width="60%" />
                <Skeleton height="14px" width="40%" />
                <div className="flex justify-between">
                  <Skeleton height="14px" width="30%" />
                  <Skeleton height="14px" width="20%" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              Welcome, {user?.name}
            </h1>
            {isConnected && (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-600">
                <span className="w-1.5 h-1.5 bg-green-500" />
                Live
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {user?.role === 'architect'
              ? 'Manage your design projects'
              : 'View your design projects'}
          </p>
        </div>
        {user?.role === 'architect' && (
          <Button onClick={() => setIsCreateOpen(true)}>New Project</Button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
        <div className="border border-border bg-white p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Total Projects
          </p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{stats.total}</p>
        </div>
        <div className="border border-border bg-white p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Active</p>
          <p className="text-3xl font-bold text-green-600 mt-1">{stats.active}</p>
        </div>
        <div className="border border-border bg-white p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Design Files</p>
          <p className="text-3xl font-bold text-primary-600 mt-1">{stats.totalFiles}</p>
        </div>
      </div>

      {projects && projects.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      ) : (
        <div className="border border-border bg-white py-12 px-6 text-center">
          <svg
            className="w-10 h-10 text-gray-300 mx-auto mb-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
            />
          </svg>
          <p className="text-gray-900 font-medium mb-1">No projects yet</p>
          {user?.role === 'architect' ? (
            <>
              <p className="text-gray-500 text-sm mb-4">Create your first project to get started</p>
              <Button onClick={() => setIsCreateOpen(true)}>Create Project</Button>
            </>
          ) : (
            <p className="text-gray-500 text-sm">
              You haven&apos;t been invited to any projects yet.
            </p>
          )}
        </div>
      )}

      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="New Project">
        <form onSubmit={handleCreateProject} className="space-y-4">
          {createError && (
            <div className="p-3 bg-red-50 border border-red-200 text-sm text-red-700">
              {createError}
            </div>
          )}
          <Input
            label="Project Name"
            type="text"
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            placeholder="e.g., Riverside Residence"
            required
          />
          <Input
            label="Description (optional)"
            type="text"
            value={newProjectDesc}
            onChange={(e) => setNewProjectDesc(e.target.value)}
            placeholder="Brief project description"
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" type="button" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createMutation.isPending}>
              Create
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
