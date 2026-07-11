import apiClient from '../client';
import type {
  UploadUrlRequest,
  UploadUrlResponse,
  MultipartInitiateRequest,
  MultipartInitiateResponse,
  MultipartPartUrlsRequest,
  MultipartPartUrlsResponse,
  MultipartCompleteRequest,
  DesignFile,
  DownloadUrlResponse,
  Firm,
  CreateFirmRequest,
  User,
  UpdateFileMilestoneRequest,
} from '../../types';

// ── Files ────────────────────────────────────────────────

export async function getUploadUrl(data: UploadUrlRequest): Promise<UploadUrlResponse> {
  const response = await apiClient.post('/files/upload-url', data);
  return response.data;
}

export async function initiateMultipart(
  data: MultipartInitiateRequest,
): Promise<MultipartInitiateResponse> {
  const response = await apiClient.post('/files/multipart/initiate', data);
  return response.data;
}

export async function getPartUrls(
  uploadId: string,
  data: MultipartPartUrlsRequest,
): Promise<MultipartPartUrlsResponse> {
  const response = await apiClient.post(`/files/multipart/${uploadId}/part-urls`, data);
  return response.data;
}

export async function completeMultipart(
  uploadId: string,
  data: MultipartCompleteRequest,
): Promise<{ message: string }> {
  const response = await apiClient.post(`/files/multipart/${uploadId}/complete`, data);
  return response.data;
}

export async function abortMultipart(
  uploadId: string,
  key: string,
): Promise<{ message: string }> {
  const response = await apiClient.post(`/files/multipart/${uploadId}/abort`, { key });
  return response.data;
}

export async function uploadComplete(fileId: string): Promise<{ message: string }> {
  const response = await apiClient.post(`/files/${fileId}/upload-complete`);
  return response.data;
}

export async function getFile(fileId: string): Promise<DesignFile> {
  const response = await apiClient.get(`/files/${fileId}`);
  return response.data;
}

export async function listProjectFiles(projectId: number): Promise<DesignFile[]> {
  const response = await apiClient.get(`/projects/${projectId}/files`);
  return response.data;
}

export async function deleteFile(fileId: string): Promise<void> {
  await apiClient.delete(`/files/${fileId}`);
}

export async function getDownloadUrl(fileId: string): Promise<DownloadUrlResponse> {
  const response = await apiClient.get(`/files/${fileId}/download`);
  return response.data;
}

export async function getThumbnailUrl(
  fileId: string,
  size: 'small' | 'medium' = 'small',
): Promise<string> {
  // Returns the redirect URL directly; browser follows 302
  const response = await apiClient.get(`/files/${fileId}/thumbnail`, {
    params: { size },
    maxRedirects: 1,
  });
  return response.request?.responseURL || '';
}

// ── Firms ────────────────────────────────────────────────

export async function createFirm(data: CreateFirmRequest): Promise<Firm> {
  const response = await apiClient.post('/firms', data);
  return response.data;
}

export async function listFirms(): Promise<Firm[]> {
  const response = await apiClient.get('/firms');
  return response.data;
}

export async function getFirmMembers(firmId: number): Promise<User[]> {
  const response = await apiClient.get(`/firms/${firmId}/members`);
  return response.data;
}

export async function addFirmMember(
  firmId: number,
  email: string,
): Promise<{ message: string }> {
  const response = await apiClient.post(`/firms/${firmId}/members`, { email });
  return response.data;
}

export async function updateFileMilestone(
  fileId: string,
  data: UpdateFileMilestoneRequest,
): Promise<{ milestone_id: number | null }> {
  const response = await apiClient.patch(`/files/${fileId}`, data);
  return response.data;
}