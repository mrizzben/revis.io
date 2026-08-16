import { useEffect, useState, useCallback } from 'react';

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  duration?: number;
}

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

const typeStyles = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
};

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), toast.duration || 5000);
    return () => clearTimeout(timer);
  }, [toast, onDismiss]);

  return (
    <div
      role="status"
      className={`flex items-center justify-between px-4 py-3 border rounded-lg shadow-card animate-slide-up ${typeStyles[toast.type]}`}
    >
      <span className="text-sm">{toast.message}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="ml-3 text-current opacity-50 hover:opacity-100 cursor-pointer rounded p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-current"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    return id;
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Expose addToast globally for store integration
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__addToast = addToast;
    return () => { delete (window as unknown as Record<string, unknown>).__addToast; };
  }, [addToast]);

  if (toasts.length === 0) return null;

  return (
    <div aria-live="polite" className="fixed top-4 right-4 z-[100] flex flex-col space-y-2 max-w-sm w-full px-4 sm:px-0">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />
      ))}
    </div>
  );
}

export function useToast() {
  const showToast = (toast: Omit<Toast, 'id'>) => {
    const fn = (window as unknown as Record<string, unknown>).__addToast as
      | ((t: Omit<Toast, 'id'>) => string)
      | undefined;
    fn?.(toast);
  };
  return { showToast };
}
