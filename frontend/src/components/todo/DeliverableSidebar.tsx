/**
 * DeliverableSidebar — 三模式统一交付物侧边栏。
 *
 * 核心原则：交付物全量一致（9项），三种模式差异只在交互方式：
 * - strict: 有序推进，门禁锁定，需显式 confirm 解锁下一项
 * - moderate: 全量展示，无序，自动提取 + 建议确认
 * - free: 极简进度条模式，不打扰但可展开查看全量；原型预览始终可达
 *
 * 交付物列表完全由后端 tracker.required 驱动，前端不硬编码。
 * 只要有原型产出，任何模式都支持预览。
 */
import { CheckCircle2, Circle, Loader2, Lock, FileText, ChevronRight, Eye, BarChart3 } from 'lucide-react';
import type { ProcessConstraint, DeliverableTracker, Artifact } from '../../types/api';
import { api } from '../../api/client';
import { openPrototypeInNewTab } from './prototypePreview';

const DELIVERABLE_LABELS: Record<string, string> = {
  requirement_spec: '需求规格',
  interaction_design: '交互设计',
  ui_spec: '视觉规范',
  prototype: '原型设计',
  tech_architecture: '技术架构',
  dev_report: '开发报告',
  test_report: '测试报告',
  deploy_report: '部署报告',
  experience_card: '经验卡片',
  ui_design: 'UI设计(旧)',
};

interface DeliverableSidebarProps {
  constraint: ProcessConstraint;
  tracker: DeliverableTracker | null;
  todoId: string;
  currentPhase?: string;
  onItemClick: (artifact: Artifact) => void;
  visible: boolean;
  onToggle: () => void;
}

export function DeliverableSidebar({
  constraint, tracker, todoId, currentPhase, onItemClick, visible, onToggle,
}: DeliverableSidebarProps) {
  const prototypeStatus = tracker?.deliverables['prototype'];
  const hasPrototype = prototypeStatus === 'produced' || prototypeStatus === 'confirmed';

  // free 模式: 极简进度指示器（不打扰，但进度可见、原型可预览）
  if (constraint === 'free') {
    if (!tracker || tracker.completion_pct === 0) return null;
    return (
      <div className="flex w-10 flex-shrink-0 flex-col items-center border-l border-border bg-bg-sidebar py-3 gap-2">
        {/* 进度环 */}
        <button
          onClick={onToggle}
          title={`交付进度 ${tracker.completion_pct}%`}
          className="relative flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-bg-elevated"
        >
          <svg width="28" height="28" className="-rotate-90">
            <circle cx="14" cy="14" r="11" fill="none" stroke="currentColor" strokeWidth="2" className="text-border" />
            <circle
              cx="14" cy="14" r="11" fill="none" stroke="currentColor" strokeWidth="2"
              className="text-accent"
              strokeDasharray={`${(tracker.completion_pct / 100) * 69.1} 69.1`}
              strokeLinecap="round"
            />
          </svg>
          <span className="absolute text-[8px] font-bold text-text-secondary">{tracker.completion_pct}</span>
        </button>
        {/* 原型预览快捷入口 */}
        {hasPrototype && (
          <button
            title="预览原型"
            onClick={async () => {
              try {
                const artifacts = await api.listArtifacts(todoId);
                const match = artifacts.find((a) => a.artifact_type === 'prototype');
                if (match?.content) openPrototypeInNewTab(match.content as Record<string, unknown>);
              } catch { /* ignore */ }
            }}
            className="flex h-7 w-7 items-center justify-center rounded-md text-accent/70 transition-colors hover:bg-accent/10 hover:text-accent"
          >
            <Eye size={12} />
          </button>
        )}
      </div>
    );
  }

  // strict / moderate: 完整侧边栏
  if (!visible) {
    return (
      <button
        onClick={onToggle}
        className="flex w-8 flex-shrink-0 flex-col items-center justify-center border-l border-border bg-bg-sidebar transition-colors hover:bg-bg-elevated"
        title="展开交付物面板"
      >
        <FileText size={13} className="text-text-muted" />
      </button>
    );
  }

  // 交付物列表完全由 tracker.required 驱动
  const items = tracker?.required ?? [];

  // strict 模式: 确定当前活跃项的索引，之后的项标记为 locked
  const currentIdx = constraint === 'strict' && currentPhase && tracker
    ? items.indexOf(currentPhase)
    : -1;

  return (
    <div className="flex w-[240px] flex-shrink-0 flex-col border-l border-border bg-bg-sidebar">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <FileText size={13} className="text-accent" />
          <span className="text-xs font-medium text-text-primary">
            {constraint === 'strict' ? '交付物（按序推进）' : '交付物'}
          </span>
        </div>
        <button onClick={onToggle} className="flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary">
          <ChevronRight size={13} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {tracker && items.length > 0 ? (
          <div className="space-y-1.5">
            {items.map((type, idx) => {
              const status = tracker.deliverables[type];
              const isDone = status === 'produced' || status === 'confirmed';
              const isInProgress = status === 'in_progress';
              const isLocked = constraint === 'strict' && currentIdx >= 0 && idx > currentIdx && !isDone;
              const isCurrent = constraint === 'strict' && idx === currentIdx;
              const isPrototype = type === 'prototype';

              return (
                <div key={type} className="flex items-center gap-1">
                  <button
                    disabled={isLocked || (!isDone && !isCurrent)}
                    onClick={async () => {
                      if (!isDone) return;
                      try {
                        const artifacts = await api.listArtifacts(todoId);
                        const match = artifacts.find((a) => a.artifact_type === type);
                        if (match) onItemClick(match);
                      } catch { /* ignore */ }
                    }}
                    className={`flex flex-1 items-center gap-2.5 rounded-md p-2 text-left transition-all ${
                      isDone ? 'bg-status-done/5 hover:bg-status-done/10 cursor-pointer'
                      : isCurrent ? 'bg-accent/5 ring-1 ring-accent/20'
                      : isLocked ? 'bg-bg-primary opacity-40 cursor-not-allowed'
                      : isInProgress ? 'bg-accent/5 cursor-default'
                      : 'bg-bg-elevated cursor-default'
                    }`}
                  >
                    {isDone ? (
                      <CheckCircle2 size={13} className="flex-shrink-0 text-status-done" />
                    ) : isLocked ? (
                      <Lock size={13} className="flex-shrink-0 text-text-muted/50" />
                    ) : isInProgress ? (
                      <Loader2 size={13} className="flex-shrink-0 animate-spin text-accent" />
                    ) : isCurrent ? (
                      <Circle size={13} className="flex-shrink-0 text-accent" />
                    ) : (
                      <Circle size={13} className="flex-shrink-0 text-text-muted" />
                    )}
                    <div className="min-w-0 flex-1">
                      <span className={`text-[11px] font-medium ${
                        isDone ? 'text-status-done'
                        : isCurrent ? 'text-accent'
                        : isLocked ? 'text-text-muted/50'
                        : isInProgress ? 'text-accent'
                        : 'text-text-secondary'
                      }`}>
                        {DELIVERABLE_LABELS[type] || type}
                      </span>
                      <p className={`text-[9px] ${
                        isDone ? 'text-text-muted'
                        : isCurrent ? 'text-accent/70'
                        : 'text-text-muted/60'
                      }`}>
                        {isDone ? '已完成' : isCurrent ? '进行中' : isLocked ? '待解锁' : isInProgress ? '生成中...' : '待开始'}
                      </p>
                    </div>
                  </button>

                  {/* 原型预览按钮 — 任何模式只要有产出就可预览 */}
                  {isPrototype && isDone && (
                    <button
                      title="预览原型"
                      onClick={async () => {
                        try {
                          const artifacts = await api.listArtifacts(todoId);
                          const match = artifacts.find((a) => a.artifact_type === 'prototype');
                          if (match?.content) {
                            openPrototypeInNewTab(match.content as Record<string, unknown>);
                          }
                        } catch { /* ignore */ }
                      }}
                      className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-accent/70 transition-colors hover:bg-accent/10 hover:text-accent"
                    >
                      <Eye size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-col items-center py-6 text-center">
            <Circle size={16} className="mb-2 text-text-muted" />
            <p className="text-[11px] text-text-muted">开始对话后自动追踪交付物进度</p>
          </div>
        )}

        {/* 完成度 */}
        {tracker && tracker.completion_pct > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <div className="flex items-center justify-between text-[10px] text-text-muted">
              <span>完成度</span>
              <span className="font-medium">{tracker.completion_pct}%</span>
            </div>
            <div className="mt-1 h-1 rounded-full bg-bg-elevated">
              <div
                className="h-1 rounded-full bg-accent transition-all"
                style={{ width: `${tracker.completion_pct}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
