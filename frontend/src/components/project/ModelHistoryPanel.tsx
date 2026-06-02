/**
 * ModelHistoryPanel — 领域模型版本历史 + 回滚。
 */
import { History, RotateCcw } from 'lucide-react';
import type { DomainModelSnapshot } from '../../types/api';

interface ModelHistoryPanelProps {
  snapshots: DomainModelSnapshot[];
  currentVersion: number;
  loading: boolean;
  onRollback: (version: number) => Promise<void>;
}

const TRIGGER_LABELS: Record<string, string> = {
  extractor: '自动提取',
  manual: '手动修改',
  upgrade: '评审升级',
  rollback: '版本回滚',
};

export default function ModelHistoryPanel({ snapshots, currentVersion, loading, onRollback }: ModelHistoryPanelProps) {
  if (loading) {
    return <div className="py-4 text-center text-xs text-text-muted">加载版本历史...</div>;
  }

  // 过滤无效快照（content 为空的升级操作产生的垃圾数据）并按版本去重（保留最新）
  const validSnapshots = snapshots.filter(s => s.trigger !== 'upgrade' || s.version > 0);
  const deduped = Array.from(
    new Map(validSnapshots.map(s => [s.version, s])).values()
  );

  if (deduped.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-bg-card p-4 text-center text-xs text-text-muted">
        暂无版本历史。领域模型变更后将自动记录。
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
        <History size={12} />
        版本历史 <span className="font-normal text-text-muted">(当前 v{currentVersion})</span>
      </h3>

      <div className="space-y-1">
        {[...deduped].reverse().map((snap, i) => (
          <div
            key={`${snap.version}-${i}`}
            className="flex items-center gap-2 rounded border border-border bg-bg-card px-3 py-1.5 text-xs"
          >
            <span className="font-mono font-medium text-text-primary">v{snap.version}</span>
            <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted">
              {TRIGGER_LABELS[snap.trigger] || snap.trigger}
            </span>
            <span className="flex-1 text-[10px] text-text-muted">
              {snap.created_at ? new Date(snap.created_at).toLocaleString('zh-CN') : ''}
            </span>
            {snap.version < currentVersion && (
              <button
                onClick={() => onRollback(snap.version)}
                className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-amber-600 hover:bg-amber-50"
                title={`回滚到 v${snap.version}`}
              >
                <RotateCcw size={10} />
                回滚
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
