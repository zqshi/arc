import { useState } from 'react';
import { Clock, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import type { ReviewFeedback } from '../../types/api';

const SCOPE_LABELS: Record<string, { label: string; color: string }> = {
  additive: { label: '增量', color: 'text-green-600 bg-green-50' },
  structural: { label: '结构性', color: 'text-amber-600 bg-amber-50' },
  breaking: { label: '破坏性', color: 'text-red-600 bg-red-50' },
};

const FB_STATUS: Record<string, { icon: typeof Clock; color: string }> = {
  pending: { icon: Clock, color: 'text-amber-500' },
  accepted: { icon: CheckCircle, color: 'text-green-500' },
  deferred: { icon: Clock, color: 'text-blue-500' },
  rejected: { icon: XCircle, color: 'text-gray-400' },
};

/** 评审反馈区: 批量操作 + 列表 */
export function FeedbackSection({ feedbacks, onResolve }: { feedbacks: ReviewFeedback[]; onResolve: (id: string, action: string, note?: string) => Promise<void> }) {
  const [batchLoading, setBatchLoading] = useState<string | null>(null);
  const pendingFeedbacks = feedbacks.filter(f => f.status === 'pending');
  const pendingCount = pendingFeedbacks.length;
  const acceptedCount = feedbacks.filter(f => f.status === 'accepted').length;
  const deferredCount = feedbacks.filter(f => f.status === 'deferred').length;
  const rejectedCount = feedbacks.filter(f => f.status === 'rejected').length;

  const handleBatch = async (action: string) => {
    setBatchLoading(action);
    try {
      for (const fb of pendingFeedbacks) {
        await onResolve(fb.id, action);
      }
    } finally {
      setBatchLoading(null);
    }
  };

  return (
    <div className="mt-4 border-t border-border pt-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-[11px] font-semibold text-text-tertiary">
          评审反馈 ({pendingCount} 待处理
          {(acceptedCount + deferredCount + rejectedCount) > 0 &&
            ` · ${acceptedCount} 已接受 · ${deferredCount} 已延迟 · ${rejectedCount} 已驳回`
          })
        </h4>
        {pendingCount > 1 && (
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-text-muted mr-1">批量:</span>
            <button
              onClick={() => handleBatch('accept')}
              disabled={!!batchLoading}
              className="rounded bg-green-600 px-2 py-0.5 text-[9px] font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              {batchLoading === 'accept' ? '...' : '全部接受'}
            </button>
            <button
              onClick={() => handleBatch('defer')}
              disabled={!!batchLoading}
              className="rounded bg-blue-600 px-2 py-0.5 text-[9px] font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {batchLoading === 'defer' ? '...' : '全部延迟'}
            </button>
            <button
              onClick={() => handleBatch('reject')}
              disabled={!!batchLoading}
              className="rounded bg-gray-200 px-2 py-0.5 text-[9px] font-medium text-text-secondary hover:bg-gray-300 disabled:opacity-50"
            >
              {batchLoading === 'reject' ? '...' : '全部驳回'}
            </button>
          </div>
        )}
      </div>
      <div className="space-y-1.5 max-h-[30vh] overflow-y-auto">
        {feedbacks.map(fb => (
          <FeedbackRow key={fb.id} feedback={fb} onResolve={onResolve} />
        ))}
      </div>
    </div>
  );
}

/** 单条反馈行 (展开/折叠 + 接受/延迟/驳回) */
function FeedbackRow({ feedback, onResolve }: { feedback: ReviewFeedback; onResolve: (id: string, action: string, note?: string) => Promise<void> }) {
  const [expanded, setExpanded] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [resolved, setResolved] = useState<string | null>(null);
  const scope = SCOPE_LABELS[feedback.scope] || SCOPE_LABELS.additive;
  const status = FB_STATUS[feedback.status] || FB_STATUS.pending;
  const StatusIcon = status.icon;

  const handleResolve = async (action: string) => {
    setResolving(true);
    try {
      await onResolve(feedback.id, action);
      setResolved(action);
    } finally {
      setResolving(false);
    }
  };

  // 已处理的反馈显示结果
  const resolvedStatus = resolved || (feedback.status !== 'pending' ? feedback.status : null);

  return (
    <div className="rounded border border-border bg-bg-card text-[10px]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-bg-elevated/50"
      >
        <StatusIcon size={12} className={status.color} />
        <span className={`flex-1 truncate ${resolvedStatus ? 'text-text-muted' : 'text-text-primary'}`}>{feedback.issue.title}</span>
        <span className={`rounded px-1 py-0.5 text-[9px] font-medium ${scope.color}`}>{scope.label}</span>
        {resolvedStatus && (
          <span className={`rounded px-1.5 py-0.5 text-[9px] font-medium ${
            resolvedStatus === 'accept' || resolvedStatus === 'accepted' ? 'bg-green-50 text-green-600' :
            resolvedStatus === 'defer' || resolvedStatus === 'deferred' ? 'bg-blue-50 text-blue-600' :
            'bg-gray-100 text-gray-500'
          }`}>
            {resolvedStatus === 'accept' || resolvedStatus === 'accepted' ? '✓ 已纳入计划' :
             resolvedStatus === 'defer' || resolvedStatus === 'deferred' ? '⏳ 已延迟' : '✗ 已驳回'}
          </span>
        )}
        {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
      </button>
      {expanded && (
        <div className="border-t border-border px-2.5 py-2 space-y-1.5">
          <p className="text-text-secondary">{feedback.issue.detail}</p>
          {feedback.issue.suggestion && <p className="text-text-muted">💡 {feedback.issue.suggestion}</p>}

          {!resolvedStatus && feedback.status === 'pending' && (
            <div className="space-y-2 pt-1">
              <div className="flex gap-1.5">
                <button onClick={() => handleResolve('accept')} disabled={resolving}
                  className="rounded bg-green-600 px-2.5 py-1 text-[9px] font-medium text-white hover:bg-green-700 disabled:opacity-50">
                  {resolving ? '...' : '接受'}
                </button>
                <button onClick={() => handleResolve('defer')} disabled={resolving}
                  className="rounded bg-blue-600 px-2.5 py-1 text-[9px] font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                  {resolving ? '...' : '延迟'}
                </button>
                <button onClick={() => handleResolve('reject')} disabled={resolving}
                  className="rounded bg-gray-200 px-2.5 py-1 text-[9px] font-medium text-text-secondary hover:bg-gray-300 disabled:opacity-50">
                  {resolving ? '...' : '驳回'}
                </button>
              </div>
              <p className="text-[9px] text-text-muted leading-relaxed">
                接受 = 确认问题存在，后续优化模型时参考 · 延迟 = 当前不处理，下个版本再看 · 驳回 = 该建议不适用
              </p>
            </div>
          )}

          {resolvedStatus && (
            <p className="text-[9px] text-text-muted pt-1">
              {resolvedStatus === 'accept' || resolvedStatus === 'accepted'
                ? '✓ 已确认。后续修改领域模型时将参考此建议改进。'
                : resolvedStatus === 'defer' || resolvedStatus === 'deferred'
                ? '⏳ 已延迟到下一版本处理。'
                : '✗ 已驳回，此建议不适用于当前项目。'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
