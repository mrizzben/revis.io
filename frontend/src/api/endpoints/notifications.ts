import apiClient from '../client';
import { Notification } from '../../types';

export const listNotifications = () => apiClient.get<Notification[]>('/notifications').then((r) => r.data);

export const markNotificationRead = (id: number) => apiClient.patch(`/notifications/${id}/read`);

export const markAllNotificationsRead = () => apiClient.patch('/notifications/read-all');