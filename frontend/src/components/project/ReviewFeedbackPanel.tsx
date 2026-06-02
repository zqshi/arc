/**
 * ReviewFeedbackPanel — 领域模型评审反馈列表 + 操作。
 * 独立组件，在 DomainModelTab 中使用。
 */
import { useState } from 'react';
import { AlertTriangle, CheckCircle, Clock, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import type { ReviewFeedback, ReviewFeedbackStatus, ModelChangeScope } from '../../types/api';

interface ReviewFeedbackPanelProps {
  feedbacks: ReviewFeedback[];
  loading: boolean;
  onResolve: (feedbackId: string, action: string, note?: string) => Promise<void>;
}

const SCOPE_STYLES: Record<ModelChangeScope, { label: string; color: string }> = {
  additive: { label: '增量', color: 'text-green-600 bg-green-50' },
  structural: { label: '结构性', color: 'text-amber-600 bg-amber-50' },
  breaking: { label: '破坏性', color: 'text-red-600 bg-red-50' },
};

const STATUS_CONFIG: Record<ReviewFeedbackStatus, { icon: typeof Clock; color: string; label: string }> = {
  pending: { icon: Clock, color: 'text-amber-500', label: '待处理' },
  accepted: { icon: CheckCircle, color: 'text-green-500', label: '已接受' },
  deferred: { icon: Clock, color: 'text-blue-500', label: '已延迟' },
  rejected: { icon: XCircle, color: 'text-gray-400', label: '已驳回' },
};

export default function ReviewFeedbackPanel({ feedbacks, loading, onResolve }: ReviewFeedbackPanelProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const pendingCount = feedbacks.filter(f => f.status === 'pending').length;

  if (loading) {
    return <div className="py-4 text-center text-xs text-text-muted">加载评审反馈...</div>;
  }

  if (feedbacks.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-bg-card p-4 text-center text-xs text-text-muted">
        暂无评审反馈。执行模型验证后将自动产生。
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-text-secondary">
          评审反馈 {pendingCount > 0 && <span className="ml-1 rounded-full bg-amber-100 px-1.5 text-amber-700">{pendingCount} 待处理</span>}
        </h3>
      </div>

      {feedbacks.map(fb => {
        const expanded = expandedId === fb.id;
        const scope = SCOPE_STYLES[fb.scope] || SCOPE_STYLES.additive;
        const status = STATUS_CONFIG[fb.status] || STATUS_CONFIG.pending;
        const StatusIcon = status.icon;

        return (
          <div key={fb.id} className="rounded-lg border border-border bg-bg-card text-xs">
            <button
              onClick={() => setExpandedId(expanded ? null : fb.id)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-bg-elevated/50"
            >
              <StatusIcon size={14} className={status.color} />
              <span className="flex-1 font-medium text-text-primary truncate">{fb.issue.title}</span>
              <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${scope.color}`}>{scope.label}</span>
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {expanded && (
              <div className="border-t border-border px-3 py-2 space-y-2">
                <p className="text-text-secondary">{fb.issue.detail}</p>
                {fb.issue.suggestion && (
                  <p className="text-text-muted">💡 {fb.issue.suggestion}</p>
                )}
                <div className="flex items-center gap-1 text-[10px] text-text-muted">
                  <span>模型版本 v{fb.model_version}</span>
                  <span>·</span>
                  <span>{fb.issue.severity}</span>
                  <span>·</span>
                  <span>{fb.issue.category}</span>
                </div>

                {fb.status === 'pending' && (
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => onResolve(fb.id, 'accept', '接受并纳入升级计划')}
                      className="rounded bg-green-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-green-700"
                    >
                      接受
                    </button>
                    <button
                      onClick={() => onResolve(fb.id, 'defer', '延迟到下一版本')}
                      className="rounded bg-blue-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-blue-700"
                    >
                      延迟
                    </button>
                    <button
                      onClick={() => onResolve(fb.id, 'reject', '评审有误')}
                      className="rounded bg-gray-200 px-2 py-1 text-[10px] font-medium text-text-secondary hover:bg-gray-300"
                    >
                      驳回
                    </button>
                  </div>
                )}

                {fb.status !== 'pending' && fb.resolution_note && (
                  <p className="text-[10px] text-text-muted italic">处理备注: {fb.resolution_note}</p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
