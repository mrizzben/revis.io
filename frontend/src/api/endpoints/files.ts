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
  FileVersion,
  ComparisonResult,
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

export async function abortMultipart(uploadId: string, key: string): Promise<{ message: string }> {
  const response = await apiClient.post(`/files/multipart/${uploadId}/abort`, { key });
  return response.data;
}

export async function uploadComplete(
  fileId: string,
  key?: string,
  revisionMessage?: string,
  name?: string,
  description?: string,
): Promise<{ message: string }> {
  const response = await apiClient.post(`/files/${fileId}/upload-complete`, null, {
    params: {
      key: key || undefined,
      revision_message: revisionMessage || undefined,
      name: name || undefined,
      description: description || undefined,
    },
  });
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
  const response = await apiClient.get(`/files/${fileId}/download`, {
    params: { return_url: true },
  });
  return response.data;
}

export async function getPreviewUrl(fileId: string): Promise<string> {
  const response = await apiClient.get(`/files/${fileId}/download`, {
    params: { return_url: true, inline: true },
  });
  return response.data.url;
}

export async function getThumbnailUrl(
  fileId: string,
  size: 'small' | 'medium' = 'small',
): Promise<string> {
  const response = await apiClient.get<{ url: string }>(`/files/${fileId}/thumbnail`, {
    params: { size, return_url: true },
  });
  return response.data.url;
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

export async function addFirmMember(firmId: number, email: string): Promise<{ message: string }> {
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

// ── Revisions (T1/T2) ─────────────────────────────────────

export async function listVersions(fileId: string): Promise<FileVersion[]> {
  const response = await apiClient.get(`/files/${fileId}/versions`);
  return response.data;
}

export async function getVersionDetail(
  fileId: string,
  versionNumber: number,
): Promise<FileVersion> {
  const response = await apiClient.get(`/files/${fileId}/versions/${versionNumber}`);
  return response.data;
}

export async function downloadVersion(
  fileId: string,
  versionNumber: number,
): Promise<{ url: string }> {
  const response = await apiClient.get(`/files/${fileId}/versions/${versionNumber}/download`);
  return response.data;
}

export async function restoreVersion(fileId: string, versionNumber: number): Promise<FileVersion> {
  const response = await apiClient.post(`/files/${fileId}/versions/${versionNumber}/restore`);
  return response.data;
}

export async function issueVersion(fileId: string, versionNumber: number): Promise<FileVersion> {
  const response = await apiClient.post(`/files/${fileId}/versions/${versionNumber}/issue`);
  return response.data;
}

export async function supersedeVersion(
  fileId: string,
  versionNumber: number,
): Promise<FileVersion> {
  const response = await apiClient.post(`/files/${fileId}/versions/${versionNumber}/supersede`);
  return response.data;
}

export async function archiveVersion(fileId: string, versionNumber: number): Promise<FileVersion> {
  const response = await apiClient.post(`/files/${fileId}/versions/${versionNumber}/archive`);
  return response.data;
}

export async function setVersionReview(
  fileId: string,
  versionNumber: number,
  inReview: boolean,
): Promise<FileVersion> {
  const response = await apiClient.post(`/files/${fileId}/versions/${versionNumber}/review`, {
    in_review: inReview,
  });
  return response.data;
}

export async function updateVersionMeta(
  fileId: string,
  versionNumber: number,
  data: {
    name?: string | null;
    description?: string | null;
    milestone_id?: number | null;
    revision_message?: string | null;
  },
): Promise<FileVersion> {
  const response = await apiClient.patch(`/files/${fileId}/versions/${versionNumber}`, data);
  return response.data;
}

export async function compareVersions(
  fileId: string,
  fromVersion: number,
  toVersion: number,
): Promise<ComparisonResult> {
  const response = await apiClient.post(`/files/${fileId}/compare`, {
    from_version: fromVersion,
    to_version: toVersion,
  });
  return response.data;
}

export async function rescanVersion(
  fileId: string,
  versionNumber: number,
): Promise<{ version_number: number; scan_status: string }> {
  const response = await apiClient.post(`/files/${fileId}/versions/${versionNumber}/scan`);
  return response.data;
}
