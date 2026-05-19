import { useState, useEffect, useCallback, useRef } from 'react';
import type { Message } from '../types/api';

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

type WsEvent =
  | WsMessageEvent
  | WsStreamStartEvent
  | WsStreamChunkEvent
  | WsStreamEndEvent
  | WsErrorEvent
  | { type: 'token_expired' }
  | { type: 'ping' };

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

export function useConversationSocket(conversationId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
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
      fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/auth/refresh`, {
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
            setMessages((prev) => [...prev, data.message]);
            setIsStreaming(false);
            break;

          case 'stream_start':
            setIsStreaming(true);
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

          case 'error':
            setError(data.detail);
            setIsStreaming(false);
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
    }
  }, []);

  const retryTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [retryDisabled, setRetryDisabled] = useState(false);

  const retry = useCallback(() => {
    if (retryDisabled) return;
    setError(null);
    setRetryDisabled(true);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'retry' }));
    }
    retryTimer.current = setTimeout(() => setRetryDisabled(false), 5000);
  }, [retryDisabled]);

  useEffect(() => {
    return () => clearTimeout(retryTimer.current);
  }, []);

  return { messages, setMessages, isConnected, isStreaming, error, sendMessage, retry, retryDisabled };
}
