import { useRef, useEffect } from 'react';
import { Bot, RefreshCw, Package } from 'lucide-react';
import MarkdownContent from '../MarkdownContent';
import { ExperienceRefBadge } from './ExperienceRefBadge';
import type { Message, ExperienceRef } from '../../types/api';

const DELIVERABLE_LABELS: Record<string, string> = {
  requirement_spec: '需求规格',
  ui_design: 'UI设计',
  tech_architecture: '技术架构',
  dev_report: '开发报告',
  test_report: '测试报告',
  deploy_report: '部署报告',
  experience_card: '经验卡片',
};

const DELIVERABLE_BLOCK_RE = /\[DELIVERABLE:([\w_]+)\]\s*```(?:json)?\s*[\s\S]*?```/g;

function processDeliverableMarkers(content: string): { cleanContent: string; deliverables: string[] } {
  const deliverables: string[] = [];
  const cleanContent = content.replace(DELIVERABLE_BLOCK_RE, (_, type: string) => {
    deliverables.push(type);
    return '';
  }).trim();
  return { cleanContent, deliverables };
}

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
      {filtered.map((msg) => {
        const isAssistant = msg.role === 'assistant';
        const { cleanContent, deliverables } = isAssistant
          ? processDeliverableMarkers(msg.content)
          : { cleanContent: msg.content, deliverables: [] };

        return (
          <div
            key={msg.id}
            className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            {isAssistant && (
              <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md bg-accent/15">
                <Bot size={11} className="text-accent" />
              </div>
            )}
            <div className="max-w-[85%]">
              {cleanContent && (
                <div
                  className={`rounded-lg px-3 py-2 text-xs leading-relaxed ${
                    isAssistant
                      ? 'bg-bg-card text-text-secondary'
                      : 'bg-accent-subtle text-text-primary'
                  }`}
                >
                  {isAssistant ? (
                    <MarkdownContent content={cleanContent} />
                  ) : (
                    <div className="whitespace-pre-wrap">{cleanContent}</div>
                  )}
                </div>
              )}
              {deliverables.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {deliverables.map((type) => (
                    <div
                      key={type}
                      className="flex items-center gap-1.5 rounded-md border border-accent/20 bg-accent/5 px-2.5 py-1.5"
                    >
                      <Package size={11} className="text-accent" />
                      <span className="text-[11px] font-medium text-accent">
                        {DELIVERABLE_LABELS[type] || type} 已生成
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {isAssistant && Array.isArray(msg.metadata?.referenced_experiences) && (
                <ExperienceRefBadge
                  refs={msg.metadata.referenced_experiences as ExperienceRef[]}
                  todoId={todoId}
                />
              )}
            </div>
          </div>
        );
      })}
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
