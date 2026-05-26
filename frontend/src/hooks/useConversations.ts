import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';
import type { Conversation } from '../types/api';

export function useConversations(todoId: string) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeConvRef = useRef(activeConversation);
  activeConvRef.current = activeConversation;

  const fetchConversations = useCallback(async () => {
    if (!todoId) return;

    setLoading(true);
    setError(null);

    try {
      const data = await api.listConversations(todoId);
      setConversations(data);

      if (data.length > 0) {
        const activeStillExists =
          activeConvRef.current && data.some((c) => c.id === activeConvRef.current!.id);

        if (!activeStillExists) {
          setActiveConversation(data[data.length - 1]);
        }
      } else {
        setActiveConversation(null);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载会话失败';
      setError(message);
      setConversations([]);
      setActiveConversation(null);
    } finally {
      setLoading(false);
    }
  }, [todoId]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const selectConversation = useCallback(
    (conversation: Conversation | null) => {
      setActiveConversation(conversation);
    },
    [],
  );

  return {
    conversations,
    activeConversation,
    setActiveConversation: selectConversation,
    loading,
    error,
    refresh: fetchConversations,
  };
}
