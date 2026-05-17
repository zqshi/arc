import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { Conversation } from '../types/api';

export function useConversations(todoId: string) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(async () => {
    if (!todoId) return;

    setLoading(true);
    setError(null);

    try {
      const data = await api.listConversations(todoId);
      setConversations(data);

      // Auto-select the latest conversation if none is active,
      // or if the currently active one no longer exists in the list
      if (data.length > 0) {
        const activeStillExists =
          activeConversation && data.some((c) => c.id === activeConversation.id);

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
  }, [todoId]); // eslint-disable-line react-hooks/exhaustive-deps
  // activeConversation intentionally excluded to prevent infinite fetch loops

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
