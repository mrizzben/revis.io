import { create } from 'zustand';

export interface Toast {
  id: string;
  type: 'file_uploaded' | 'file_deleted' | 'file_updated' | 'milestone_updated' | 'comment_added' | 'error';
  title: string;
  message: string;
  timestamp: number;
}

interface NotificationState {
  toasts: Toast[];
  pushNotification: (type: Toast['type'], title: string, message: string) => void;
  dismissNotification: (id: string) => void;
  clearAll: () => void;
}

const TOAST_DURATION = 5_000;

export const useNotifications = create<NotificationState>((set) => ({
  toasts: [],

  pushNotification: (type, title, message) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const toast: Toast = { id, type, title, message, timestamp: Date.now() };

    set((state) => ({ toasts: [...state.toasts, toast] }));

    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }));
    }, TOAST_DURATION);
  },

  dismissNotification: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },

  clearAll: () => {
    set({ toasts: [] });
  },
}));
