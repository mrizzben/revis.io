import apiClient from '../client';
import { Comment } from '../../types';

export const listComments = (fileId: string) =>
  apiClient.get<Comment[]>(`/files/${fileId}/comments`).then(r => r.data);

export const createComment = (fileId: string, data: { body: string; parent_id?: number }) =>
  apiClient.post<Comment>(`/files/${fileId}/comments`, data).then(r => r.data);

export const updateComment = (id: number, data: { body?: string; is_resolved?: boolean }) =>
  apiClient.patch<Comment>(`/comments/${id}`, data).then(r => r.data);

export const deleteComment = (id: number) =>
  apiClient.delete(`/comments/${id}`);
