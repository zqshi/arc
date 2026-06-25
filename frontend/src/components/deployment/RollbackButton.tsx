import { useState } from 'react';
import { RotateCcw, AlertTriangle } from 'lucide-react';
import { api } from '../../api/client';
import type { Deployment } from '../../types/api';

interface Props {
  projectId: string;
  versionId: string;
  /** 已知 deployment_id 时直接用；否则组件自动查 latest */
  deploymentId?: string;
  onRolledBack?: (deployment: Deployment) => void;
}

/**
 * v5.5.0: 部署回滚按钮。
 *
 * 行为：点击 → 确认弹窗 → 调 rollbackDeployment → 回调通知。
 * 若当前部署已 rolled_back 则禁用。
 */
export default function RollbackButton({ projectId, versionId, deploymentId, onRolledBack }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [rolling, setRolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState<Deployment | null>(null);

  const handleClick = async () => {
    setError(null);
    if (!confirming) {
      setConfirming(true);
      // 预查 latest deployment 状态，用于确认弹窗展示 + 已回滚则禁用
      try {
        const dep = await api.getLatestDeployment(projectId, versionId);
        setCurrent(dep);
        if (dep.status === 'rolled_back') {
          // 已回滚，直接展示禁用态，不进确认
          setConfirming(false);
        }
      } catch {
        // 无部署记录，忽略 — 用户点确认时再报错
      }
      return;
    }
    // 确认 → 执行回滚
    setRolling(true);
    try {
      const targetId = deploymentId ?? current?.id;
      if (!targetId) {
        setError('未找到可回滚的部署记录');
        setRolling(false);
        return;
      }
      const updated = await api.rollbackDeployment(projectId, targetId);
      setCurrent(updated);
      setConfirming(false);
      onRolledBack?.(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : '回滚失败');
    } finally {
      setRolling(false);
    }
  };

  const isRolledBack = current?.status === 'rolled_back';

  if (isRolledBack && !confirming) {
    return (
      <span className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-[11px] text-text-muted">
        <AlertTriangle size={12} /> 已回滚
      </span>
    );
  }

  if (confirming) {
    return (
      <span className="flex items-center gap-2">
        <span className="text-[11px] text-status-warning">确认回滚此部署？</span>
        <button
          onClick={handleClick}
          disabled={rolling}
          className="rounded-md bg-status-error px-2 py-1 text-[11px] font-medium text-white transition-colors hover:bg-status-error/90 disabled:opacity-50"
        >
          {rolling ? '回滚中...' : '确认回滚'}
        </button>
        <button
          onClick={() => { setConfirming(false); setError(null); }}
          disabled={rolling}
          className="rounded-md px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-bg-elevated disabled:opacity-50"
        >
          取消
        </button>
        {error && <span className="text-[11px] text-status-error">{error}</span>}
      </span>
    );
  }

  return (
    <button
      onClick={handleClick}
      className="flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:bg-bg-elevated hover:text-status-warning"
      title="回滚到此前部署"
    >
      <RotateCcw size={12} /> 回滚部署
    </button>
  );
}
