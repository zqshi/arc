import { useEffect, useRef, useCallback, useState } from 'react';
import { api } from '../api/client';
import type { TaskStreamEvent } from '../types/api';

export interface TaskState {
  status: 'idle' | 'running' | 'error';
  stage: string;
  lastContent: string;
  artifacts: string[];
}

const DEFAULT_STATE: TaskState = {
  status: 'idle',
  stage: '',
  lastContent: '',
  artifacts: [],
};

export function useProjectTaskStream(projectId: string | undefined) {
  const [taskStates, setTaskStates] = useState<Map<string, TaskState>>(new Map());
  const [connected, setConnected] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleEvent = useCallback((event: TaskStreamEvent) => {
    if (event.event === 'connected') {
      setConnected(true);
      return;
    }

    const todoId = event.todo_id;
    if (!todoId) return;

    setTaskStates((prev) => {
      const next = new Map(prev);
      const current = next.get(todoId) || { ...DEFAULT_STATE };

      switch (event.event) {
        case 'task_status':
          current.status = event.status || 'idle';
          current.stage = event.stage || '';
          if (event.status === 'idle') {
            current.lastContent = '';
          }
          break;
        case 'task_chunk':
          current.lastContent += event.content || '';
          break;
        case 'task_done':
          current.status = 'idle';
          current.stage = '已完成';
          current.artifacts = event.artifacts || [];
          break;
      }

      next.set(todoId, { ...current });
      return next;
    });
  }, []);

  useEffect(() => {
    if (!projectId) return;

    const controller = new AbortController();
    abortRef.current = controller;

    api.subscribeTaskStream(projectId, handleEvent, controller.signal);

    return () => {
      controller.abort();
      abortRef.current = null;
      setConnected(false);
    };
  }, [projectId, handleEvent]);

  const getTaskState = useCallback(
    (todoId: string): TaskState => taskStates.get(todoId) || DEFAULT_STATE,
    [taskStates],
  );

  return { taskStates, getTaskState, connected };
}
