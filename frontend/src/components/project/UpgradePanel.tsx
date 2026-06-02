/**
 * UpgradePanel — 领域模型升级操作面板。
 * 当有已接受的评审反馈时显示，支持：
 * 1. 触发影响分析
 * 2. 查看影响报告
 * 3. 选择策略执行升级
 */
import { useState } from 'react';
import { Zap, AlertTriangle, Loader2, Shield, Clock } from 'lucide-react';
import { api } from '../../api/client';
import type { ReviewFeedback, ImpactReport } from '../../types/api';

interface UpgradePanelProps {
  projectId: string;
  acceptedFeedbacks: ReviewFeedback[];
  currentModelVersion: number;
  onUpgradeComplete: () => void;
}

export default function UpgradePanel({ projectId, acceptedFeedbacks, currentModelVersion, onUpgradeComplete }: UpgradePanelProps) {
  const [impactReport, setImpactReport] = useState<ImpactReport | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [error, setError] = useState('');

  if (acceptedFeedbacks.length === 0) return null;

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setError('');
    try {
      // 从 accepted feedbacks 中提取受影响聚合名称
      const aggregates = Array.from(new Set(
        acceptedFeedbacks.flatMap(f => {
          const detail = f.issue.detail || '';
          // 简单提取 PascalCase 名称作为聚合候选
          return detail.match(/[A-Z][a-z]+(?:[A-Z][a-z]+)*/g) || [];
        })
      ));
      const scope = acceptedFeedbacks.some(f => f.scope === 'breaking') ? 'breaking'
        : acceptedFeedbacks.some(f => f.scope === 'structural') ? 'structural' : 'additive';

      const report = await api.analyzeModelImpact(projectId, aggregates.length > 0 ? aggregates : ['_all'], scope);
      setImpactReport(report);
    } catch (e) {
      setError('影响分析失败，请稍后重试');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleUpgrade = async (strategy: 'block' | 'defer') => {
    setUpgrading(true);
    setError('');
    try {
      const feedbackIds = acceptedFeedbacks.map(f => f.id);
      // 传当前模型作为 new_model（实际升级应由后端基于反馈生成新模型，此处简化为触发）
      await api.executeModelUpgrade(projectId, feedbackIds, {} as any, strategy);
      onUpgradeComplete();
    } catch (e) {
      setError('升级执行失败');
    } finally {
      setUpgrading(false);
    }
  };

  return (
    <div className="rounded-lg border border-accent/30 bg-accent/5 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-xs font-semibold text-accent">
          <Zap size={13} />
          待执行升级 ({acceptedFeedbacks.length} 条已接受反馈)
        </h3>
        {!impactReport && (
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-[10px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {analyzing ? <Loader2 size={10} className="animate-spin" /> : <Shield size={10} />}
            影响分析
          </button>
        )}
      </div>

      {error && <p className="text-[10px] text-status-error">{error}</p>}

      {/* Impact Report */}
      {impactReport && (
        <div className="space-y-2">
          <p className="text-[11px] text-text-secondary">{impactReport.summary}</p>

          {impactReport.items.length > 0 && (
            <div className="space-y-1">
              {impactReport.items.map((item, i) => (
                <div key={i} className="flex items-center gap-2 rounded border border-border bg-bg-card px-3 py-1.5 text-[10px]">
                  <span className={`rounded px-1.5 py-0.5 font-medium ${
                    item.risk === 'critical' || item.risk === 'high'
                      ? 'bg-red-50 text-red-600'
                      : item.risk === 'medium' ? 'bg-amber-50 text-amber-600'
                      : 'bg-green-50 text-green-600'
                  }`}>
                    {item.risk}
                  </span>
                  <span className="flex-1 text-text-primary truncate">{item.todo_title}</span>
                  <span className="text-text-muted">{item.current_phase}</span>
                </div>
              ))}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-2">
            <button
              onClick={() => handleUpgrade('block')}
              disabled={upgrading}
              className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-[10px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {upgrading ? <Loader2 size={10} className="animate-spin" /> : <Zap size={10} />}
              立即升级{impactReport.blocked_count > 0 ? `（暂停 ${impactReport.blocked_count} 个需求）` : ''}
            </button>
            <button
              onClick={() => handleUpgrade('defer')}
              disabled={upgrading}
              className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-[10px] font-medium text-text-secondary hover:bg-bg-elevated disabled:opacity-50"
            >
              <Clock size={10} /> 延迟到下一版本
            </button>
          </div>

          {impactReport.blocked_count > 0 && (
            <p className="text-[9px] text-text-muted">
              ⚠️ "立即升级"将暂停 {impactReport.blocked_count} 个高风险需求，升级完成后可手动恢复。
            </p>
          )}
        </div>
      )}
    </div>
  );
}
