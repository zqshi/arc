/**
 * DeliverableSidebar — 三模式配置化交付物侧边栏。
 *
 * - strict: 全量 8 项，有序，当前高亮，未到灰色，需 confirm 解锁下一项
 * - moderate: 4 项核心，无序，可自由点击
 * - free: 折叠/隐藏，仅在有产出时显示极简通知
 */
import { CheckCircle2, Circle, Loader2, Lock, FileText, ChevronRight, ExternalLink } from 'lucide-react';
import type { ProcessConstraint, DeliverableTracker, Artifact } from '../../types/api';
import { PHASE_ORDER } from '../../types/api';
import { api } from '../../api/client';

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

// strict 模式按阶段顺序展示全量
const STRICT_ORDER = [
  'requirement_spec', 'interaction_design', 'tech_architecture',
  'dev_report', 'test_report', 'deploy_report', 'experience_card',
];

// moderate 模式只展示核心四项
const MODERATE_ITEMS = ['requirement_spec', 'tech_architecture', 'dev_report', 'test_report'];

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
  // free 模式: 不展示侧边栏
  if (constraint === 'free') {
    return null;
  }

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

  const items = constraint === 'strict' ? STRICT_ORDER : MODERATE_ITEMS;
  const filteredItems = items.filter((type) =>
    tracker ? tracker.required.includes(type) || tracker.deliverables[type] : true
  );

  // strict 模式: 确定当前活跃项的索引，之后的项标记为 locked
  const currentIdx = constraint === 'strict' && currentPhase
    ? STRICT_ORDER.indexOf(currentPhase)
    : -1;

  return (
    <div className="flex w-[240px] flex-shrink-0 flex-col border-l border-border bg-bg-sidebar">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <FileText size={13} className="text-accent" />
          <span className="text-xs font-medium text-text-primary">
            {constraint === 'strict' ? '交付物（按序推进）' : '核心交付物'}
          </span>
        </div>
        <button onClick={onToggle} className="flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary">
          <ChevronRight size={13} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {tracker ? (
          <div className="space-y-1.5">
            {filteredItems.map((type, idx) => {
              const status = tracker.deliverables[type];
              const isDone = status === 'produced' || status === 'confirmed';
              const isInProgress = status === 'in_progress';
              const isLocked = constraint === 'strict' && currentIdx >= 0 && idx > currentIdx && !isDone;
              const isCurrent = constraint === 'strict' && idx === currentIdx;

              return (
                <button
                  key={type}
                  disabled={isLocked || (!isDone && !isCurrent)}
                  onClick={async () => {
                    if (!isDone) return;
                    try {
                      const artifacts = await api.listArtifacts(todoId);
                      const match = artifacts.find((a) => a.artifact_type === type);
                      if (match) onItemClick(match);
                    } catch { /* ignore */ }
                  }}
                  className={`flex w-full items-center gap-2.5 rounded-md p-2 text-left transition-all ${
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
