import apiClient from '../client';
import type { Milestone } from '../../types';

export async function listMilestones(projectId: number): Promise<Milestone[]> {
  const response = await apiClient.get<Milestone[]>(`/projects/${projectId}/milestones`);
  return response.data;
}

export async function createMilestone(
  projectId: number,
  data: { name: string; description?: string; position?: number },
): Promise<Milestone> {
  const response = await apiClient.post<Milestone>(`/projects/${projectId}/milestones`, data);
  return response.data;
}

export async function updateMilestone(
  id: number,
  data: { name?: string; description?: string; position?: number; is_completed?: boolean },
): Promise<Milestone> {
  const response = await apiClient.patch<Milestone>(`/milestones/${id}`, data);
  return response.data;
}

export async function deleteMilestone(id: number): Promise<void> {
  await apiClient.delete(`/milestones/${id}`);
}
