import { useState, useEffect, useCallback, useRef } from 'react';
import type { Message } from '../types/api';
import { quotaEvents } from '../lib/quota-events';

const WS_BASE = import.meta.env.VITE_WS_URL || `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;

interface WsMessageEvent {
  type: 'message';
  message: Message;
}

interface WsStreamStartEvent {
  type: 'stream_start';
  message_id: string;
}

interface WsStreamChunkEvent {
  type: 'stream_chunk';
  message_id: string;
  content: string;
}

interface WsStreamEndEvent {
  type: 'stream_end';
  message_id: string;
}

interface WsErrorEvent {
  type: 'error';
  detail: string;
}

interface WsArtifactsExtractedEvent {
  type: 'artifacts_extracted';
  artifacts: string[];
  artifact_names: string[];
  tracker?: {
    required: string[];
    deliverables: Record<string, string>;
    completion_pct: number;
    is_complete: boolean;
  };
}

interface WsToolCallEvent {
  type: 'tool_call';
  message_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  round: number;
  parallel?: boolean;
}

interface WsToolResultEvent {
  type: 'tool_result';
  message_id: string;
  tool_name: string;
  output_preview: string;
  is_error: boolean;
  parallel?: boolean;
}

interface WsToolErrorEvent {
  type: 'tool_error';
  message_id: string;
  detail: string;
}

interface WsQuotaExceededEvent {
  type: 'quota_exceeded';
  detail: string;
}

interface WsApprovalRequiredEvent {
  type: 'approval_required';
  request_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface ApprovalInfo {
  request_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface ToolCallInfo {
  id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  output_preview?: string;
  is_error?: boolean;
  status: 'running' | 'done';
  parallel?: boolean;
  round?: number;
}

type WsEvent =
  | WsMessageEvent
  | WsStreamStartEvent
  | WsStreamChunkEvent
  | WsStreamEndEvent
  | WsErrorEvent
  | WsArtifactsExtractedEvent
  | WsToolCallEvent
  | WsToolResultEvent
  | WsToolErrorEvent
  | WsQuotaExceededEvent
  | WsApprovalRequiredEvent
  | { type: 'stream_resume'; message_id: string; buffered_content: string }
  | { type: 'orchestration_start'; plan_id: string; subtask_count: number }
  | { type: 'worker_start'; worker_id: string; plan_id: string; subtask: { description: string; task_type: string } }
  | { type: 'worker_complete'; worker_id: string; output_preview: string; tokens_used: number; elapsed_ms: number }
  | { type: 'worker_error'; worker_id: string; error: string }
  | { type: 'synthesis_start'; plan_id: string }
  | { type: 'orchestration_complete'; plan_id: string; total_tokens: number; worker_count: number }
  | { type: 'token_expired' }
  | { type: 'ping' };

export interface WorkerInfo {
  id: string;
  description: string;
  task_type: string;
  status: 'pending' | 'running' | 'done' | 'error';
  output_preview?: string;
  tokens_used?: number;
  elapsed_ms?: number;
}

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

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;

        let data: WsEvent;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }

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
            break;

          case 'stream_start':
            setIsStreaming(true);
            setToolCalls([]); // 新一轮开始时清空上一轮工具记录
            break;

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
            break;

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
            break;

          case 'stream_end':
            setIsStreaming(false);
            break;

          case 'quota_exceeded':
            quotaEvents.emit(data.detail);
            setIsStreaming(false);
            break;

          case 'error':
            setError(data.detail);
            setIsStreaming(false);
            break;

          case 'artifacts_extracted':
            setArtifactsVersion((v) => v + 1);
            // 如果后端携带了 tracker 快照，直接通知上层更新（避免额外 API 往返）
            if (data.tracker) {
              trackerSnapshotRef.current = data.tracker;
            }
            break;

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
            break;

          case 'tool_result': {
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
            break;
          }

          case 'tool_error':
            setError(data.detail);
            setIsStreaming(false);
            break;

          case 'approval_required':
            setPendingApproval({
              request_id: data.request_id,
              tool_name: data.tool_name,
              tool_input: data.tool_input,
            });
            break;

          case 'orchestration_start':
            setWorkers([]);
            setOrchestrationPhase('working');
            break;

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
            break;

          case 'worker_complete':
            setWorkers((prev) =>
              prev.map((w) =>
                w.id === data.worker_id
                  ? { ...w, status: 'done' as const, output_preview: data.output_preview, tokens_used: data.tokens_used, elapsed_ms: data.elapsed_ms }
                  : w
              )
            );
            break;

          case 'worker_error':
            setWorkers((prev) =>
              prev.map((w) =>
                w.id === data.worker_id ? { ...w, status: 'error' as const, output_preview: data.error } : w
              )
            );
            break;

          case 'synthesis_start':
            setOrchestrationPhase('synthesizing');
            break;

          case 'orchestration_complete':
            setOrchestrationPhase('complete');
            break;
        }
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
