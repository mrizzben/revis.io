import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import useAuthStore from '../stores/authStore';
import { useNotifications } from '../stores/notificationStore';
import { checkUpdates } from '../api/endpoints/projects';
import type { WsEvent } from '../types';

interface UseWebSocketReturn {
  isConnected: boolean;
  isPolling: boolean;
  lastEvent: WsEvent | null;
}

const POLL_INTERVAL = 10_000;
const RECONNECT_POLL_INTERVAL = 30_000;
const ERROR_DEBOUNCE = 5_000;
const INITIAL_BACKOFF = 1_000;
const MAX_BACKOFF = 30_000;

function jitter(base: number): number {
  return base * (0.75 + Math.random() * 0.5);
}

export default function useWebSocket(projectId: number | null): UseWebSocketReturn {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF);
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastTimestampRef = useRef<string | undefined>(undefined);

  const { pushNotification } = useNotifications();

  const [isConnected, setIsConnected] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);

  const clearPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    if (reconnectIntervalRef.current) {
      clearInterval(reconnectIntervalRef.current);
      reconnectIntervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const startPolling = useCallback(() => {
    if (!projectId) return;
    clearPolling();

    setIsPolling(true);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const result = await checkUpdates(projectId, lastTimestampRef.current);
        lastTimestampRef.current = result.timestamp;
        if (result.has_updates) {
          queryClient.invalidateQueries({ queryKey: ['files', projectId] });
          queryClient.invalidateQueries({ queryKey: ['milestones', projectId] });
        }
      } catch {
        // Ignore polling errors
      }
    }, POLL_INTERVAL);

    reconnectIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        clearPolling();
      }
    }, RECONNECT_POLL_INTERVAL);
  }, [projectId, clearPolling, queryClient]);

  const connect = useCallback(() => {
    if (!projectId || !accessToken) return;

    const wsUrl = import.meta.env.VITE_WS_URL || window.location.host;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${wsUrl}/ws/projects/${projectId}?token=${accessToken}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      clearPolling();
      backoffRef.current = INITIAL_BACKOFF;
      setIsConnected(true);
      if (errorTimerRef.current) {
        clearTimeout(errorTimerRef.current);
        errorTimerRef.current = null;
      }
      queryClient.invalidateQueries({ queryKey: ['files', projectId] });
      queryClient.invalidateQueries({ queryKey: ['milestones', projectId] });
    };

    ws.onmessage = (event) => {
      try {
        const data: WsEvent = JSON.parse(event.data);
        setLastEvent(data);

        switch (data.type) {
          case 'file_uploaded':
          case 'file_deleted':
            queryClient.invalidateQueries({ queryKey: ['files', projectId] });
            break;
          case 'file_updated':
            queryClient.invalidateQueries({ queryKey: ['files', projectId] });
            queryClient.invalidateQueries({ queryKey: ['project', projectId] });
            if (data.file_id) {
              queryClient.invalidateQueries({ queryKey: ['file', data.file_id] });
            }
            break;
          case 'milestone_updated':
            queryClient.invalidateQueries({ queryKey: ['milestones', projectId] });
            break;
          case 'comment_added':
            if (data.file_id) {
              queryClient.invalidateQueries({ queryKey: ['comments', data.file_id] });
            }
            pushNotification('comment_added', 'New comment', 'A new comment was added');
            break;
          case 'internal_note_added':
            queryClient.invalidateQueries({ queryKey: ['internal-notes', projectId] });
            pushNotification('mention', 'Internal note', 'A teammate added an internal note');
            break;
          case 'todo_added':
          case 'todo_updated':
          case 'todo_deleted':
            queryClient.invalidateQueries({ queryKey: ['todos', projectId] });
            if (data.type !== 'todo_deleted') {
              pushNotification('todo_assigned', 'To-do updated', 'A teammate updated a to-do');
            }
            break;
          case 'ping':
            ws.send(JSON.stringify({ type: 'pong' }));
            break;
        }
      } catch {
        // Ignore parse errors
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, jitter(backoffRef.current));
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF);
    };

    ws.onerror = () => {
      if (!errorTimerRef.current) {
        errorTimerRef.current = setTimeout(() => {
          if (wsRef.current?.readyState !== WebSocket.OPEN) {
            startPolling();
          }
        }, ERROR_DEBOUNCE);
      }
    };
  }, [projectId, accessToken, queryClient, clearPolling, startPolling, pushNotification]);

  useEffect(() => {
    if (!projectId) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      clearPolling();
      setIsConnected(false);
      return;
    }

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      clearPolling();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
    };
  }, [projectId, connect, clearPolling]);

  return { isConnected, isPolling, lastEvent };
}
