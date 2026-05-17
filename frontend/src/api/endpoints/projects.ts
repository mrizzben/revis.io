import apiClient from '../client';
import type {
  Project,
  ProjectDetail,
  CreateProjectRequest,
  UpdateProjectRequest,
  Invitation,
  InvitationDetail,
  InviteClientRequest,
  ProjectUpdatesResponse,
} from '../../types';

export async function listProjects(archived = false): Promise<Project[]> {
  const response = await apiClient.get('/projects', { params: { archived } });
  return response.data;
}

export async function createProject(data: CreateProjectRequest): Promise<Project> {
  const response = await apiClient.post('/projects', data);
  return response.data;
}

export async function getProject(projectId: number): Promise<ProjectDetail> {
  const response = await apiClient.get(`/projects/${projectId}`);
  return response.data;
}

export async function updateProject(
  projectId: number,
  data: UpdateProjectRequest,
): Promise<Project> {
  const response = await apiClient.patch(`/projects/${projectId}`, data);
  return response.data;
}

export async function deleteProject(
  projectId: number,
  archiveOnly = true,
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}`, {
    params: { archive_only: archiveOnly },
  });
}

export async function inviteClient(
  projectId: number,
  data: InviteClientRequest,
): Promise<Invitation> {
  const response = await apiClient.post(`/projects/${projectId}/invite`, data);
  return response.data;
}

export async function getInvitation(token: string): Promise<InvitationDetail> {
  const response = await apiClient.get(`/invitations/${token}`);
  return response.data;
}

export async function checkUpdates(
  projectId: number,
  since?: string,
): Promise<ProjectUpdatesResponse> {
  const response = await apiClient.get(`/projects/${projectId}/updates`, {
    params: { since },
  });
  return response.data;
}
