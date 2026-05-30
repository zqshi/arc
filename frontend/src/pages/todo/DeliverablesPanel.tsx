import {
  FileText,
  Lightbulb,
  Loader2,
  ChevronRight,
  CheckCircle2,
  Circle,
  ExternalLink,
} from 'lucide-react';
import { api } from '../../api/client';
import type {
  Experience,
  DeliverableTracker,
  Artifact,
} from '../../types/api';
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
  // Legacy
  ui_design: 'UI设计(旧)',
};

interface DeliverablesPanelProps {
  todoId: string;
  tracker: DeliverableTracker | null;
  showRight: boolean;
  setShowRight: (v: boolean) => void;
  relatedExps: Experience[];
  onSelectExp: (exp: Experience) => void;
  onOpenArtifact: (artifact: Artifact) => void;
  isCompact: boolean;
}

export function DeliverablesPanel({
  todoId,
  tracker,
  showRight,
  setShowRight,
  relatedExps,
  onSelectExp,
  onOpenArtifact,
  isCompact,
}: DeliverablesPanelProps) {
  if (isCompact) return null;

  if (!showRight) {
    return (
      <div className="flex w-10 flex-shrink-0 flex-col items-center border-l border-border bg-bg-sidebar py-3">
        <button
          onClick={() => setShowRight(true)}
          title="展开交付物面板"
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-card hover:text-accent"
        >
          <FileText size={14} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-[260px] flex-shrink-0 flex-col border-l border-border bg-bg-sidebar">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <FileText size={13} className="text-accent" />
          <span className="text-xs font-medium text-text-primary">交付物</span>
        </div>
        <button
          onClick={() => setShowRight(false)}
          className="flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary"
        >
          <ChevronRight size={13} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-3">
        {tracker ? (
          <div className="space-y-2">
            {tracker.required.map((type) => {
              const status = tracker.deliverables[type];
              const isDone = status === 'produced' || status === 'confirmed';
              const isInProgress = status === 'in_progress';
              return (
                <div key={type} className="flex items-center gap-1">
                  <button
                    disabled={!isDone}
                    onClick={async () => {
                      if (!isDone || !todoId) return;
                      try {
                        const artifacts = await api.listArtifacts(todoId);
                        const match = artifacts.find((a) => a.artifact_type === type);
                        if (match) onOpenArtifact(match);
                      } catch {
                        /* ignore */
                      }
                    }}
                    className={`flex flex-1 items-center gap-2.5 rounded-md p-2.5 text-left transition-colors ${
                      isDone
                        ? 'bg-status-done/5 hover:bg-status-done/10 cursor-pointer'
                        : isInProgress
                          ? 'bg-accent/5 cursor-default'
                          : 'bg-bg-elevated cursor-default'
                    }`}
                  >
                    {isDone ? (
                      <CheckCircle2 size={14} className="flex-shrink-0 text-status-done" />
                    ) : isInProgress ? (
                      <Loader2 size={14} className="flex-shrink-0 animate-spin text-accent" />
                    ) : (
                      <Circle size={14} className="flex-shrink-0 text-text-muted" />
                    )}
                    <div className="min-w-0 flex-1">
                      <span
                        className={`text-[11px] font-medium ${
                          isDone
                            ? 'text-status-done'
                            : isInProgress
                              ? 'text-accent'
                              : 'text-text-secondary'
                        }`}
                      >
                        {DELIVERABLE_LABELS[type] || type}
                      </span>
                      {isDone ? (
                        <p className="text-[9px] text-text-muted">点击预览</p>
                      ) : isInProgress ? (
                        <p className="text-[9px] text-accent/70">生成中...</p>
                      ) : (
                        <p className="text-[9px] text-text-muted">待生成</p>
                      )}
                    </div>
                  </button>
                  {type === 'prototype' && isDone && (
                    <PrototypePreviewButton todoId={todoId} />
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-[11px] text-text-muted">暂无交付物信息</p>
        )}
        {tracker && tracker.is_complete && (
          <div className="mt-4 rounded-md border border-status-done/30 bg-status-done/5 p-3 text-center">
            <CheckCircle2 size={20} className="mx-auto mb-1 text-status-done" />
            <p className="text-xs font-medium text-status-done">全部交付物已完成</p>
          </div>
        )}
      </div>

      {relatedExps.length > 0 && (
        <div className="border-t border-border px-3 pt-2 pb-3">
          <div className="mb-1 flex items-center gap-1 px-1">
            <Lightbulb size={10} className="text-accent" />
            <span className="text-[9px] font-medium text-text-tertiary">相关经验</span>
          </div>
          {relatedExps.slice(0, 2).map((exp) => (
            <button
              key={exp.id}
              onClick={() => onSelectExp(exp)}
              className="mb-1 w-full rounded px-1.5 py-1 text-left text-[10px] text-text-secondary transition-colors hover:bg-bg-elevated"
            >
              <span className="line-clamp-1">{exp.title}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function PrototypePreviewButton({ todoId }: { todoId: string }) {
  return (
    <button
      title="产品预览"
      onClick={async (e) => {
        e.stopPropagation();
        if (!todoId) return;
        try {
          const artifacts = await api.listArtifacts(todoId);
          const match = artifacts.find((a) => a.artifact_type === 'prototype');
          if (!match) return;
          if (match.preview_url) {
            window.open(match.preview_url, '_blank');
          } else {
            const result = await api.publishArtifact(todoId, match.id);
            if (result.preview_url) {
              window.open(result.preview_url, '_blank');
            } else if (match.content) {
              openPrototypeInNewTab(match.content as Record<string, unknown>);
            }
          }
        } catch {
          try {
            const artifacts = await api.listArtifacts(todoId);
            const match = artifacts.find((a) => a.artifact_type === 'prototype');
            if (match?.content) openPrototypeInNewTab(match.content as Record<string, unknown>);
          } catch {
            /* ignore */
          }
        }
      }}
      className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md text-accent transition-colors hover:bg-accent/10"
    >
      <ExternalLink size={13} />
    </button>
  );
}
