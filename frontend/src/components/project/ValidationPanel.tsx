/**
 * ValidationPanel — AI 评审结果弹窗。
 * 支持 stale 状态下的"模型已变更"警告 + 重新评审按钮。
 */
import { useState } from 'react';
import { ShieldCheck, X, AlertTriangle, Loader2, RefreshCw, CheckCircle2, Info, Clock, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import type { DomainModelValidation, ReviewFeedback, ReviewFeedbackStatus, ModelChangeScope } from '../../types/api';
import type { ReviewState } from '../../hooks/useDomainModelReview';

const LEVEL_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  excellent: { label: '优秀', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  good: { label: '良好', color: 'text-blue-600', bg: 'bg-blue-50' },
  needs_improvement: { label: '待改进', color: 'text-amber-600', bg: 'bg-amber-50' },
  poor: { label: '较差', color: 'text-red-600', bg: 'bg-red-50' },
};

const SEVERITY_CONFIG: Record<string, { icon: typeof AlertTriangle; color: string; bg: string; border: string }> = {
  error: { icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' },
  warning: { icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200' },
  info: { icon: Info, color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200' },
};

interface ValidationPanelProps {
  validation: DomainModelValidation;
  onClose?: () => void;
  reviewState: ReviewState;
  lastReviewedVersion: number;
  currentVersion: number;
  onRevalidate: () => Promise<void>;
  revalidating: boolean;
  feedbacks: ReviewFeedback[];
  onResolveFeedback: (feedbackId: string, action: string, note?: string) => Promise<void>;
}

export default function ValidationPanel({
  validation, onClose, reviewState, lastReviewedVersion, currentVersion, onRevalidate, revalidating, feedbacks, onResolveFeedback,
}: ValidationPanelProps) {
  const levelStyle = LEVEL_STYLES[validation.level] || LEVEL_STYLES.poor;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative mx-4 w-full max-w-2xl animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="flex items-center gap-2 font-heading text-sm font-semibold text-text-primary">
            <ShieldCheck size={14} className="text-accent" /> DDD 领域模型评审
            {lastReviewedVersion > 0 && (
              <span className="rounded-full bg-bg-elevated px-2 py-0.5 text-[10px] font-normal text-text-muted">
                v{lastReviewedVersion}
              </span>
            )}
          </h2>
          <button
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:text-text-secondary"
          >
            <X size={14} />
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">
          {/* Stale warning */}
          {reviewState === 'stale' && (
            <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-2.5">
              <div className="flex items-center gap-2 text-xs text-amber-600">
                <AlertTriangle size={14} />
                <span>模型已从 v{lastReviewedVersion} 更新到 v{currentVersion}，评审结果可能已过时</span>
              </div>
              <button
                onClick={onRevalidate}
                disabled={revalidating}
                className="flex items-center gap-1 rounded-md bg-amber-500 px-3 py-1 text-[10px] font-medium text-white hover:bg-amber-600 disabled:opacity-50"
              >
                {revalidating ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
                重新评审
              </button>
            </div>
          )}

          {/* Score */}
          <div className="mb-4 flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-bold ${levelStyle.color}`}>{validation.score}</span>
              <span className="text-xs text-text-muted">/ 100</span>
            </div>
            <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${levelStyle.color} ${levelStyle.bg}`}>
              {levelStyle.label}
            </span>
          </div>

          {/* Summary */}
          <p className="mb-4 text-xs leading-relaxed text-text-secondary">{validation.summary}</p>

          {/* Strengths */}
          {validation.strengths.length > 0 && (
            <div className="mb-4">
              <h4 className="mb-2 text-[11px] font-semibold text-text-tertiary">优势</h4>
              <div className="space-y-1">
                {validation.strengths.map((s, i) => (
                  <div key={i} className="flex items-start gap-2 text-[11px]">
                    <CheckCircle2 size={12} className="mt-0.5 flex-shrink-0 text-emerald-500" />
                    <span className="text-text-secondary">{s}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Issues */}
          {validation.issues.length > 0 && (
            <div>
              <h4 className="mb-2 text-[11px] font-semibold text-text-tertiary">
                问题 ({validation.issues.filter(i => i.severity === 'error').length} 错误,{' '}
                {validation.issues.filter(i => i.severity === 'warning').length} 警告,{' '}
                {validation.issues.filter(i => i.severity === 'info').length} 建议)
              </h4>
              <div className="space-y-2">
                {validation.issues.map((issue, i) => {
                  const cfg = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.info;
                  const Icon = cfg.icon;
                  return (
                    <div key={i} className={`rounded-lg border ${cfg.border} p-3 ${cfg.bg}`}>
                      <div className="flex items-center gap-2">
                        <Icon size={12} className={cfg.color} />
                        <span className={`text-[11px] font-semibold ${cfg.color}`}>{issue.title}</span>
                        <span className="rounded border border-border bg-bg-card px-1.5 py-0.5 text-[9px] text-text-secondary">{issue.category}</span>
                      </div>
                      <p className="mt-1 pl-5 text-[10px] text-text-primary">{issue.detail}</p>
                      {issue.suggestion && (
                        <p className="mt-1 pl-5 text-[10px] text-accent">→ {issue.suggestion}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Feedback Actions */}
          {feedbacks.length > 0 && (
            <div className="mt-4 border-t border-border pt-4">
              <h4 className="mb-2 text-[11px] font-semibold text-text-tertiary">
                评审反馈 ({feedbacks.filter(f => f.status === 'pending').length} 待处理
                {feedbacks.filter(f => f.status !== 'pending').length > 0 &&
                  ` · ${feedbacks.filter(f => f.status === 'accepted').length} 已接受 · ${feedbacks.filter(f => f.status === 'deferred').length} 已延迟 · ${feedbacks.filter(f => f.status === 'rejected').length} 已驳回`
                })
              </h4>
              <div className="space-y-1.5 max-h-[30vh] overflow-y-auto">
                {feedbacks.map(fb => (
                  <FeedbackRow key={fb.id} feedback={fb} onResolve={onResolveFeedback} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

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
