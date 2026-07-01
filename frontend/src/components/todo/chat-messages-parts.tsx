import { Bot, Package, RefreshCw } from 'lucide-react';
import MarkdownContent from '../MarkdownContent';
import HtmlApplyButton from '../prototype/HtmlApplyButton';
import { ExperienceRefBadge } from './ExperienceRefBadge';
import { ToolCallsCollapsed } from './ToolCallDisplay';
import type { Message, ExperienceRef } from '../../types/api';

export const DELIVERABLE_LABELS: Record<string, string> = {
  requirement_spec: '需求规格',
  interaction_design: '交互设计',
  ui_spec: '视觉规范',
  prototype: '原型设计',
  tech_architecture: '技术架构',
  dev_report: '开发报告',
  test_report: '测试报告',
  deploy_report: '部署报告',
  experience_card: '经验卡片',
  ui_design: 'UI设计',
};

const DELIVERABLE_BLOCK_RE = /\[DELIVERABLE:([\w_]+)\]\s*```(?:json)?\s*[\s\S]*?```/g;

export function processDeliverableMarkers(content: string): { cleanContent: string; deliverables: string[] } {
  const deliverables: string[] = [];
  const cleanContent = content.replace(DELIVERABLE_BLOCK_RE, (_, type: string) => {
    deliverables.push(type);
    return '';
  }).trim();
  return { cleanContent, deliverables };
}

/** 单条消息气泡 (含交付物标记、经验引用、历史工具调用) */
export function MessageBubble({ msg, todoId }: { msg: Message; todoId: string }) {
  const isAssistant = msg.role === 'assistant';
  const { cleanContent, deliverables } = isAssistant
    ? processDeliverableMarkers(msg.content)
    : { cleanContent: msg.content, deliverables: [] };

  return (
    <div className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
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
              <>
                <MarkdownContent content={cleanContent} />
                <HtmlApplyButton content={cleanContent} onApply={(html) => {
                  // 广播 HTML — prototype 交互渲染功能未接线, 此广播暂无接收方 (待产品决策是否恢复)
                  window.postMessage({ type: 'arc_apply_prototype_html', html }, '*');
                }} />
              </>
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
        {/* 历史消息中的工具调用记录 */}
        {isAssistant && Array.isArray(msg.metadata?.tool_calls) && msg.metadata.tool_calls.length > 0 && (
          <ToolCallsCollapsed
            toolCalls={msg.metadata.tool_calls.map((tc: Record<string, unknown>, i: number) => ({
              id: `hist-${msg.id}-${i}`,
              tool_name: (tc.tool_name as string) || '',
              tool_input: { path: tc.tool_input_summary || '' },
              output_preview: (tc.output_preview as string) || '',
              is_error: !!tc.is_error,
              status: 'done' as const,
            }))}
          />
        )}
      </div>
    </div>
  );
}

/** 流式指示器 + 错误重试块 */
export function StreamingAndError({
  isStreaming,
  error,
  onRetry,
  retryDisabled,
  hideStreamingIndicator,
}: {
  isStreaming: boolean;
  error: string | null;
  onRetry: () => void;
  retryDisabled: boolean;
  hideStreamingIndicator?: boolean;
}) {
  return (
    <>
      {isStreaming && !hideStreamingIndicator && (
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
    </>
  );
}
