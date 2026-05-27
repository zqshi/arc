import type {
  SystemSettings,
  BatchStartResult,
  QuickMessageResponse,
  TaskStreamEvent,
  UsageResponse,
  PlanLimitsResponse,
} from '../../types/api';
import type { RequestFn, ScanEvent } from './base';

export function createSystemMethods(request: RequestFn, base: string) {
  return {
    getSettings: (): Promise<SystemSettings> =>
      request('/api/settings'),

    browseDirectory: (path: string = '~'): Promise<{ current: string; parent: string | null; dirs: string[] }> =>
      request(`/api/filesystem/browse?path=${encodeURIComponent(path)}`),

    createDirectory: (path: string): Promise<{ path: string }> =>
      request('/api/filesystem/mkdir', { method: 'POST', body: JSON.stringify({ path }) }),

    scanCodebase: (projectId: string, force = false): Promise<{ summary?: string; cached?: boolean; task_id?: string; status?: string }> => {
      const params = force ? '?force=true' : '';
      return request(`/api/projects/${projectId}/scan-codebase${params}`, { method: 'POST' });
    },

    scanCodebaseStream(projectId: string, onEvent: (event: ScanEvent) => void, signal?: AbortSignal): void {
      const token = localStorage.getItem('access_token');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      fetch(`${base}/api/projects/${projectId}/scan-codebase/stream`, {
        headers,
        signal,
      }).then(async (resp) => {
        if (!resp.ok || !resp.body) {
          onEvent({ event: 'error', detail: `HTTP ${resp.status}` });
          return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          let currentEvent = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7);
            } else if (line.startsWith('data: ')) {
              const data = line.slice(6);
              try {
                const parsed = JSON.parse(data);
                onEvent({ event: currentEvent || parsed.event, ...parsed });
              } catch {
                // skip malformed data
              }
              currentEvent = '';
            }
          }
        }

        onEvent({ event: 'close' });
      }).catch((err) => {
        if (err.name !== 'AbortError') {
          onEvent({ event: 'error', detail: err.message || '连接失败' });
        }
      });
    },

    batchStartConversations: (projectId: string, todoIds: string[]): Promise<{ results: BatchStartResult[] }> =>
      request(`/api/projects/${projectId}/batch-start-conversations`, { method: 'POST', body: JSON.stringify({ todo_ids: todoIds }) }),

    sendQuickMessage: (todoId: string, content: string): Promise<QuickMessageResponse> =>
      request(`/api/todos/${todoId}/quick-message`, { method: 'POST', body: JSON.stringify({ content }) }),

    subscribeTaskStream(
      projectId: string,
      onEvent: (event: TaskStreamEvent) => void,
      signal?: AbortSignal,
    ): void {
      const token = localStorage.getItem('access_token');
      const url = `${base}/api/projects/${projectId}/task-stream`;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      let retries = 0;
      const maxRetries = 5;
      const baseDelay = 2000;

      const connect = () => {
        if (signal?.aborted) return;

        fetch(url, { headers, signal }).then(async (resp) => {
          if (!resp.ok || !resp.body) {
            onEvent({ event: 'error', detail: `HTTP ${resp.status}` });
            return;
          }

          retries = 0;
          const reader = resp.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          let currentEvent = '';
          let lastActivity = Date.now();

          const heartbeatCheck = setInterval(() => {
            if (Date.now() - lastActivity > 60_000) {
              clearInterval(heartbeatCheck);
              reader.cancel();
            }
          }, 15_000);

          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              lastActivity = Date.now();
              buffer += decoder.decode(value, { stream: true });

              const lines = buffer.split('\n');
              buffer = lines.pop() || '';

              for (const line of lines) {
                if (line.startsWith('event: ')) {
                  currentEvent = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                  const data = line.slice(6);
                  if (currentEvent === 'ping') { currentEvent = ''; continue; }
                  try {
                    const parsed = JSON.parse(data);
                    onEvent({ event: (currentEvent || 'connected') as TaskStreamEvent['event'], ...parsed });
                  } catch {
                    // skip malformed
                  }
                  currentEvent = '';
                }
              }
            }
          } finally {
            clearInterval(heartbeatCheck);
          }

          if (!signal?.aborted && retries < maxRetries) {
            retries++;
            setTimeout(connect, baseDelay * retries);
          }
        }).catch((err) => {
          if (err.name === 'AbortError') return;
          onEvent({ event: 'error', detail: err.message || '连接失败' });
          if (retries < maxRetries) {
            retries++;
            setTimeout(connect, baseDelay * retries);
          }
        });
      };

      connect();
    },

    getUsage: (): Promise<UsageResponse> =>
      request('/api/billing/usage'),

    getPlanLimits: (): Promise<PlanLimitsResponse> =>
      request('/api/billing/plans'),
  };
}
