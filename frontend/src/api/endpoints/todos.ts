import apiClient from '../client';
import type { ToDo } from '../../types';

export const listTodos = (projectId: number) =>
  apiClient.get<ToDo[]>(`/projects/${projectId}/todos`).then((r) => r.data);

export const createTodo = (
  projectId: number,
  data: { title: string; description?: string | null; assignee_id?: number | null },
) => apiClient.post<ToDo>(`/projects/${projectId}/todos`, data).then((r) => r.data);

export const updateTodo = (
  projectId: number,
  todoId: number,
  data: {
    title?: string;
    description?: string | null;
    status?: 'open' | 'complete';
    assignee_id?: number | null;
  },
) => apiClient.patch<ToDo>(`/projects/${projectId}/todos/${todoId}`, data).then((r) => r.data);

export const deleteTodo = (projectId: number, todoId: number) =>
  apiClient.delete(`/projects/${projectId}/todos/${todoId}`);
