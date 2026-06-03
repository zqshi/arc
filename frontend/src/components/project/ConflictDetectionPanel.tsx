import { useState } from 'react';
import { Shield, AlertTriangle, CheckCircle2, ArrowRight, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import { useToast } from '../Toast';
import type { ConflictAnalysis, ConflictItem } from '../../types/api';

interface ConflictDetectionPanelProps {
  projectId: string;
  versionId: string;
}

export function ConflictDetectionPanel({ projectId, versionId }: ConflictDetectionPanelProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ConflictAnalysis | null>(null);

  const handleDetect = async () => {
    setLoading(true);
    try {
      const data = await api.detectConflicts(projectId, versionId);
      setResult(data);
    } catch {
      toast('冲突检测失败', 'error');
    } finally {
      setLoading(false);
    }
  };

  if (!result) {
    return (
      <button
        onClick={handleDetect}
        disabled={loading}
        className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[11px] font-medium text-text-secondary transition-colors hover:bg-bg-elevated disabled:opacity-40"
      >
        {loading ? (
          <><Loader2 size={12} className="animate-spin" /> 分析中...</>
        ) : (
          <><Shield size={12} /> 冲突检测</>
        )}
      </button>
    );
  }

  const hasConflicts = result.conflicts.length > 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {hasConflicts ? (
            <AlertTriangle size={13} className="text-amber-500" />
          ) : (
            <CheckCircle2 size={13} className="text-green-500" />
          )}
          <span className="text-[11px] font-medium text-text-primary">
            {hasConflicts ? `发现 ${result.conflicts.length} 个潜在冲突` : '未发现冲突'}
          </span>
        </div>
        <button
          onClick={handleDetect}
          disabled={loading}
          className="text-[10px] text-text-muted hover:text-text-secondary"
        >
          <RefreshIcon loading={loading} />
        </button>
      </div>

      {result.risk_summary && (
        <p className="text-[11px] text-text-muted">{result.risk_summary}</p>
      )}

      {result.conflicts.map((conflict, i) => (
        <ConflictCard key={i} conflict={conflict} />
      ))}

      {result.sequential_required.length > 0 && (
        <div className="rounded-md border border-border bg-bg-elevated p-3 space-y-2">
          <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wide">建议执行顺序</p>
          {result.sequential_required.map((seq, i) => (
            <div key={i} className="flex items-center gap-2 text-[11px] text-text-secondary">
              <span className="font-medium">{seq.first}</span>
              <ArrowRight size={10} className="text-text-muted" />
              <span className="font-medium">{seq.then}</span>
              <span className="text-text-muted">({seq.reason})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ConflictCard({ conflict }: { conflict: ConflictItem }) {
  const severityStyles = {
    high: 'border-red-500/30 bg-red-500/5',
    medium: 'border-amber-500/30 bg-amber-500/5',
    low: 'border-blue-500/20 bg-blue-500/5',
  };
  const severityLabels = { high: '高', medium: '中', low: '低' };
  const typeLabels = {
    write_conflict: '写冲突',
    cross_aggregate: '跨聚合',
    new_aggregate: '新增聚合',
  };

  return (
    <div className={`rounded-md border p-3 space-y-1.5 ${severityStyles[conflict.severity]}`}>
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-bg-card px-1.5 py-0.5 text-[9px] font-medium">
          {typeLabels[conflict.type]}
        </span>
        <span className="rounded-full bg-bg-card px-1.5 py-0.5 text-[9px] font-medium">
          风险: {severityLabels[conflict.severity]}
        </span>
        {conflict.aggregate && (
          <span className="text-[10px] text-text-muted">聚合: {conflict.aggregate}</span>
        )}
      </div>
      <p className="text-[11px] text-text-primary">{conflict.description}</p>
      <div className="flex flex-wrap gap-1">
        {conflict.features.map((f) => (
          <span key={f} className="rounded bg-bg-card px-1.5 py-0.5 text-[10px] text-text-secondary">
            {f}
          </span>
        ))}
      </div>
      {conflict.suggestion && (
        <p className="text-[10px] text-text-muted italic">💡 {conflict.suggestion}</p>
      )}
    </div>
  );
}

function RefreshIcon({ loading }: { loading: boolean }) {
  if (loading) return <Loader2 size={11} className="animate-spin" />;
  return <span>重新检测</span>;
}
