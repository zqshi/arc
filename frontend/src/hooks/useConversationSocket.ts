import { useState, useEffect, useCallback, useRef } from 'react';
import type { Message } from '../types/api';
import { quotaEvents } from '../lib/quota-events';

const WS_BASE = import.meta.env.VITE_WS_URL || `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;

import type {
  WsEvent,
  ApprovalInfo,
  ToolCallInfo,
  WorkerInfo,
} from './conversation-socket-types';

export type { ApprovalInfo, ToolCallInfo, WorkerInfo } from './conversation-socket-types';

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

export function useConversationSocket(conversationId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [artifactsVersion, setArtifactsVersion] = useState(0);
  const [toolCalls, setToolCalls] = useState<ToolCallInfo[]>([]);
  const [pendingApproval, setPendingApproval] = useState<ApprovalInfo | null>(null);
  const [workers, setWorkers] = useState<WorkerInfo[]>([]);
  const [orchestrationPhase, setOrchestrationPhase] = useState<'idle' | 'working' | 'synthesizing' | 'complete'>('idle');

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  // artifacts_extracted 事件携带的 tracker 快照（避免额外 API 往返）
  const trackerSnapshotRef = useRef<{
    required: string[];
    deliverables: Record<string, string>;
    completion_pct: number;
    is_complete: boolean;
  } | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    setMessages([]);
    setIsConnected(false);
    setIsStreaming(false);
    setError(null);

    if (!conversationId) {
      return;
    }

    function refreshTokenAndReconnect() {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        setError('登录已过期，请重新登录');
        return;
      }
      fetch(`${import.meta.env.VITE_API_URL || ''}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((data) => {
          if (data.access_token) {
            localStorage.setItem('access_token', data.access_token);
            reconnectAttempt.current = 0;
            setTimeout(connect, 500);
          }
        })
        .catch(() => {
          setError('登录已过期，请重新登录');
        });
    }

    function connect() {
      if (!mountedRef.current) return;

      const token = localStorage.getItem('access_token');
      const url = token
        ? `${WS_BASE}/ws/conversations/${conversationId}?token=${encodeURIComponent(token)}`
        : `${WS_BASE}/ws/conversations/${conversationId}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        setError(null);
        reconnectAttempt.current = 0;
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        setIsStreaming(false);

        if (event.code === 4002) {
          refreshTokenAndReconnect();
          return;
        }

        const delay =
          RECONNECT_DELAYS[
            Math.min(reconnectAttempt.current, RECONNECT_DELAYS.length - 1)
          ];
        reconnectAttempt.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        if (!mountedRef.current) return;
        setError('WebSocket 连接异常');
      };

      function handleMessageEvent(data: WsEvent) {
        switch (data.type) {
          case 'ping':
            ws.send(JSON.stringify({ type: 'pong' }));
            return;
          case 'token_expired':
            ws.close();
            refreshTokenAndReconnect();
            return;
          case 'message':
            setMessages((prev) => {
              if (prev.some((m) => m.id === data.message.id)) return prev;
              return [...prev, data.message];
            });
            setIsStreaming(false);
            return;

          case 'quota_exceeded':
            quotaEvents.emit(data.detail);
            setIsStreaming(false);
            return;

          case 'error':
            setError(data.detail);
            setIsStreaming(false);
            return;

          case 'artifacts_extracted':
            setArtifactsVersion((v) => v + 1);
            // 如果后端携带了 tracker 快照，直接通知上层更新（避免额外 API 往返）
            if (data.tracker) {
              trackerSnapshotRef.current = data.tracker;
            }
            return;
        }
      }

      function handleStreamEvent(data: WsEvent) {
        switch (data.type) {
          case 'stream_start':
            setIsStreaming(true);
            setToolCalls([]); // 新一轮开始时清空上一轮工具记录
            return;

          case 'stream_resume':
            // 重连后恢复流式状态 — 合并已缓冲的内容
            setIsStreaming(true);
            if (data.buffered_content) {
              setMessages((prev) => {
                if (prev.some((m) => m.id === data.message_id)) {
                  // 已有该消息（比如 stream_chunk 已创建），更新内容
                  return prev.map((m) =>
                    m.id === data.message_id
                      ? { ...m, content: data.buffered_content }
                      : m
                  );
                }
                return [
                  ...prev,
                  {
                    id: data.message_id,
                    conversation_id: conversationId!,
                    role: 'assistant' as const,
                    content: data.buffered_content,
                    created_at: new Date().toISOString(),
                  },
                ];
              });
            }
            return;

          case 'stream_chunk':
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'assistant' && last.id === data.message_id) {
                // Append to existing streaming message
                return [
                  ...prev.slice(0, -1),
                  { ...last, content: last.content + data.content },
                ];
              }
              // First chunk - create new message placeholder
              return [
                ...prev,
                {
                  id: data.message_id,
                  conversation_id: conversationId!,
                  role: 'assistant' as const,
                  content: data.content,
                  created_at: new Date().toISOString(),
                },
              ];
            });
            return;

          case 'stream_end':
            setIsStreaming(false);
            return;
        }
      }

      function handleToolEvent(data: WsEvent) {
        switch (data.type) {
          case 'tool_call':
            setToolCalls((prev) => [
              ...prev,
              {
                id: `${data.round}-${data.tool_name}-${prev.length}`,
                tool_name: data.tool_name,
                tool_input: data.tool_input,
                status: 'running',
                parallel: data.parallel,
                round: data.round,
              },
            ]);
            return;

          case 'tool_result':
            setToolCalls((prev) => {
              let matched = false;
              return prev.map((tc) => {
                if (!matched && tc.tool_name === data.tool_name && tc.status === 'running') {
                  matched = true;
                  return { ...tc, output_preview: data.output_preview, is_error: data.is_error, status: 'done' as const };
                }
                return tc;
              });
            });
            return;

          case 'tool_error':
            setError(data.detail);
            setIsStreaming(false);
            return;

          case 'approval_required':
            setPendingApproval({
              request_id: data.request_id,
              tool_name: data.tool_name,
              tool_input: data.tool_input,
            });
            return;
        }
      }

      function handleOrchestrationEvent(data: WsEvent) {
        switch (data.type) {
          case 'orchestration_start':
            setWorkers([]);
            setOrchestrationPhase('working');
            return;

          case 'worker_start':
            setWorkers((prev) => [
              ...prev,
              {
                id: data.worker_id,
                description: data.subtask.description,
                task_type: data.subtask.task_type,
                status: 'running',
              },
            ]);
            return;

          case 'worker_complete':
            setWorkers((prev) =>
              prev.map((w) =>
                w.id === data.worker_id
                  ? { ...w, status: 'done' as const, output_preview: data.output_preview, tokens_used: data.tokens_used, elapsed_ms: data.elapsed_ms }
                  : w
              )
            );
            return;

          case 'worker_error':
            setWorkers((prev) =>
              prev.map((w) =>
                w.id === data.worker_id ? { ...w, status: 'error' as const, output_preview: data.error } : w
              )
            );
            return;

          case 'synthesis_start':
            setOrchestrationPhase('synthesizing');
            return;

          case 'orchestration_complete':
            setOrchestrationPhase('complete');
            return;
        }
      }

      function handleEvent(data: WsEvent) {
        switch (data.type) {
          case 'ping':
          case 'token_expired':
          case 'message':
          case 'quota_exceeded':
          case 'error':
          case 'artifacts_extracted':
            handleMessageEvent(data);
            break;
          case 'stream_start':
          case 'stream_resume':
          case 'stream_chunk':
          case 'stream_end':
            handleStreamEvent(data);
            break;
          case 'tool_call':
          case 'tool_result':
          case 'tool_error':
          case 'approval_required':
            handleToolEvent(data);
            break;
          case 'orchestration_start':
          case 'worker_start':
          case 'worker_complete':
          case 'worker_error':
          case 'synthesis_start':
          case 'orchestration_complete':
            handleOrchestrationEvent(data);
            break;
        }
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;

        let data: WsEvent;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }

        handleEvent(data);
      };
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [conversationId]);

  const sendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'message', content }));
      setIsStreaming(true); // 立即展示思考状态，避免发送后无反馈
      setToolCalls([]);
      setWorkers([]);
      setOrchestrationPhase('idle');
    }
  }, []);

  const retryTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [retryDisabled, setRetryDisabled] = useState(false);

  const retry = useCallback(() => {
    if (retryDisabled) return;
    setError(null);
    setIsStreaming(true); // 立即展示思考状态
    setRetryDisabled(true);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'retry' }));
    }
    retryTimer.current = setTimeout(() => setRetryDisabled(false), 5000);
  }, [retryDisabled]);

  const respondToApproval = useCallback((requestId: string, approved: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'approval_response', request_id: requestId, approved }));
    }
    setPendingApproval(null);
  }, []);

  useEffect(() => {
    return () => clearTimeout(retryTimer.current);
  }, []);

  return { messages, setMessages, isConnected, isStreaming, error, sendMessage, retry, retryDisabled, artifactsVersion, toolCalls, pendingApproval, respondToApproval, workers, orchestrationPhase, trackerSnapshot: trackerSnapshotRef };
}
