import { useRef, useEffect } from 'react';
import { Bot, RefreshCw } from 'lucide-react';
import MarkdownContent from '../MarkdownContent';
import { ExperienceRefBadge } from './ExperienceRefBadge';
import type { Message, ExperienceRef } from '../../types/api';

interface ChatMessagesProps {
  messages: Message[];
  isStreaming: boolean;
  error: string | null;
  conversationId: string | null;
  todoId: string;
  onRetry: () => void;
  retryDisabled: boolean;
}

export function ChatMessages({
  messages,
  isStreaming,
  error,
  conversationId,
  todoId,
  onRetry,
  retryDisabled,
}: ChatMessagesProps) {
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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

  return (
    <div className="flex flex-col gap-3">
      {filtered.map((msg) => (
        <div
          key={msg.id}
          className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
        >
          {msg.role === 'assistant' && (
            <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md bg-accent/15">
              <Bot size={11} className="text-accent" />
            </div>
          )}
          <div className="max-w-[85%]">
            <div
              className={`rounded-lg px-3 py-2 text-xs leading-relaxed ${
                msg.role === 'assistant'
                  ? 'bg-bg-card text-text-secondary'
                  : 'bg-accent-subtle text-text-primary'
              }`}
            >
              {msg.role === 'assistant' ? (
                <MarkdownContent content={msg.content} />
              ) : (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              )}
            </div>
            {msg.role === 'assistant' && Array.isArray(msg.metadata?.referenced_experiences) && (
              <ExperienceRefBadge
                refs={msg.metadata.referenced_experiences as ExperienceRef[]}
                todoId={todoId}
              />
            )}
          </div>
        </div>
      ))}
      {isStreaming && (
        <div className="flex gap-2">
          <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md bg-accent/15">
            <Bot size={11} className="text-accent animate-pulse" />
          </div>
          <span className="text-[11px] text-text-muted">思考中...</span>
        </div>
      )}
      {error && (
        <div className="mx-1 rounded-md border border-status-error/30 bg-status-error/5 px-3 py-2">
          <p className="text-[11px] text-status-error">
            {error.includes('暂时不可用')
              ? '⚡ AI 服务暂时过载，请稍后重试'
              : error.includes('超时')
              ? '⏱ AI 响应超时，请简化问题后重试'
              : `⚠ ${error}`}
          </p>
          <button
            onClick={onRetry}
            disabled={isStreaming || retryDisabled}
            className="mt-1.5 flex items-center gap-1 rounded-md bg-status-error/10 px-2.5 py-1 text-[11px] font-medium text-status-error transition-colors hover:bg-status-error/20 disabled:opacity-50"
          >
            <RefreshCw size={11} className={retryDisabled ? 'animate-spin' : ''} />
            {retryDisabled ? '请求中...' : '重新生成'}
          </button>
        </div>
      )}
      <div ref={chatEndRef} />
    </div>
  );
}
