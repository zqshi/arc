import { useRef, useEffect, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Bot } from 'lucide-react';
import type { Message } from '../../types/api';
import { MessageBubble, StreamingAndError } from './chat-messages-parts';

interface ChatMessagesProps {
  messages: Message[];
  isStreaming: boolean;
  error: string | null;
  conversationId: string | null;
  todoId: string;
  onRetry: () => void;
  retryDisabled: boolean;
  /** 当外部有工具调用等进度指示时，隐藏内部的"思考中..."避免重复 */
  hideStreamingIndicator?: boolean;
}

const VIRTUAL_THRESHOLD = 80;

export function ChatMessages({
  messages,
  isStreaming,
  error,
  conversationId,
  todoId,
  onRetry,
  retryDisabled,
  hideStreamingIndicator,
}: ChatMessagesProps) {
  const filtered = messages.filter((m) => m.role !== 'system');

  if (filtered.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-2 text-center">
        <Bot size={20} className="mb-2 text-accent/30" />
        <p className="text-[11px] text-text-muted">
          {conversationId ? '对话即将开始...' : '启动阶段后可与AI对话'}
        </p>
      </div>
    );
  }

  if (filtered.length >= VIRTUAL_THRESHOLD) {
    return (
      <VirtualizedMessages
        filtered={filtered}
        isStreaming={isStreaming}
        error={error}
        todoId={todoId}
        onRetry={onRetry}
        retryDisabled={retryDisabled}
        hideStreamingIndicator={hideStreamingIndicator}
      />
    );
  }

  return (
    <SimpleMessages
      filtered={filtered}
      isStreaming={isStreaming}
      error={error}
      todoId={todoId}
      onRetry={onRetry}
      retryDisabled={retryDisabled}
      hideStreamingIndicator={hideStreamingIndicator}
    />
  );
}

function SimpleMessages({
  filtered,
  isStreaming,
  error,
  todoId,
  onRetry,
  retryDisabled,
  hideStreamingIndicator,
}: {
  filtered: Message[];
  isStreaming: boolean;
  error: string | null;
  todoId: string;
  onRetry: () => void;
  retryDisabled: boolean;
  hideStreamingIndicator?: boolean;
}) {
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [filtered]);

  return (
    <div className="flex flex-col gap-3">
      {filtered.map((msg) => (
        <MessageBubble key={msg.id} msg={msg} todoId={todoId} />
      ))}
      <StreamingAndError
        isStreaming={isStreaming}
        error={error}
        onRetry={onRetry}
        retryDisabled={retryDisabled}
        hideStreamingIndicator={hideStreamingIndicator}
      />
      <div ref={chatEndRef} />
    </div>
  );
}

function VirtualizedMessages({
  filtered,
  isStreaming,
  error,
  todoId,
  onRetry,
  retryDisabled,
  hideStreamingIndicator,
}: {
  filtered: Message[];
  isStreaming: boolean;
  error: string | null;
  todoId: string;
  onRetry: () => void;
  retryDisabled: boolean;
  hideStreamingIndicator?: boolean;
}) {
  const parentRef = useRef<HTMLDivElement>(null);

  const totalCount = filtered.length + (isStreaming || error ? 1 : 0);

  const virtualizer = useVirtualizer({
    count: totalCount,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 10,
  });

  const scrollToBottom = useCallback(() => {
    if (totalCount > 0) {
      virtualizer.scrollToIndex(totalCount - 1, { align: 'end', behavior: 'smooth' });
    }
  }, [virtualizer, totalCount]);

  useEffect(() => {
    scrollToBottom();
  }, [filtered.length, isStreaming, scrollToBottom]);

  return (
    <div ref={parentRef} className="h-full overflow-auto">
      <div
        className="relative w-full"
        style={{ height: `${virtualizer.getTotalSize()}px` }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const isLast = virtualRow.index >= filtered.length;
          return (
            <div
              key={virtualRow.key}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              className="absolute left-0 top-0 w-full py-1.5"
              style={{ transform: `translateY(${virtualRow.start}px)` }}
            >
              {isLast ? (
                <StreamingAndError
                  isStreaming={isStreaming}
                  error={error}
                  onRetry={onRetry}
                  retryDisabled={retryDisabled}
                  hideStreamingIndicator={hideStreamingIndicator}
                />
              ) : (
                <MessageBubble msg={filtered[virtualRow.index]} todoId={todoId} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
