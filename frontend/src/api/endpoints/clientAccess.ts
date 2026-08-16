import apiClient from '../client';
import type {
  ClientAccessInfo,
  ClientAccessAuth,
  ClientAccessAuthResponse,
  ClientAccessSetupResponse,
} from '../../types';

export async function getClientAccessInfo(token: string): Promise<ClientAccessInfo> {
  const response = await apiClient.get(`/client-access/${token}`);
  return response.data;
}

export async function authenticateClientAccess(
  data: ClientAccessAuth,
): Promise<ClientAccessAuthResponse> {
  const response = await apiClient.post('/client-access/authenticate', data);
  return response.data;
}

export async function configureClientAccess(
  projectId: number,
  password?: string,
): Promise<ClientAccessSetupResponse> {
  const response = await apiClient.post(`/projects/${projectId}/client-access`, {
    password: password ?? null,
  });
  return response.data;
}

export async function disableClientAccess(projectId: number): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/client-access`);
}
