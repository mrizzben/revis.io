import apiClient from '../client';
import type { CollaboratorsResponse } from '../../types';

export const listCollaborators = (projectId: number) =>
  apiClient.get<CollaboratorsResponse>(`/projects/${projectId}/collaborators`).then((r) => r.data);

export const addCollaborator = (projectId: number, data: { email?: string; user_id?: number }) =>
  apiClient.post(`/projects/${projectId}/collaborators`, data).then((r) => r.data);

export const removeCollaborator = (projectId: number, userId: number) =>
  apiClient.delete(`/projects/${projectId}/collaborators/${userId}`);
