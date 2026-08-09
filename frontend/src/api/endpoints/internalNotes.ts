import apiClient from '../client';
import type { InternalNote, InternalNotesResponse } from '../../types';

export const listInternalNotes = (projectId: number) =>
  apiClient.get<InternalNotesResponse>(`/projects/${projectId}/internal-notes`).then((r) => r.data);

export const createInternalNote = (projectId: number, data: { body: string; mentions: number[] }) =>
  apiClient.post<InternalNote>(`/projects/${projectId}/internal-notes`, data).then((r) => r.data);

export const createInternalNoteReply = (projectId: number, noteId: number, body: string) =>
  apiClient
    .post(`/projects/${projectId}/internal-notes/${noteId}/replies`, { body })
    .then((r) => r.data);
