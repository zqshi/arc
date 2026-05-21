import { useState, useEffect, useCallback } from 'react';
import { BarChart3, GitBranch, Clock, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import type { ProjectDashboard } from '../../types/api';

interface DashboardTabProps {
  projectId: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-text-muted',
  active: 'bg-accent',
  done: 'bg-status-done',
  error: 'bg-status-error',
};

export function DashboardTab({ projectId }: DashboardTabProps) {
  const [data, setData] = useState<ProjectDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    try {
      const d = await api.getProjectDashboard(projectId);
      setData(d);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 size={20} className="animate-spin text-accent" />
      </div>
    );
  }

  if (!data) {
    return <div className="py-8 text-center text-sm text-text-muted">暂无数据</div>;
  }

  const { todo_stats, version_progress, agent_stats, recent_activity } = data;

  return (
    <div className="space-y-6 p-4">
      {/* Todo Stats */}
      <section>
        <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold text-text-primary">
          <BarChart3 size={14} className="text-accent" /> 需求概览
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="待处理" value={todo_stats.pending} color="text-text-muted" />
          <StatCard label="进行中" value={todo_stats.active} color="text-accent" />
          <StatCard label="已完成" value={todo_stats.done} color="text-status-done" />
          <StatCard label="异常" value={todo_stats.error} color="text-status-error" />
        </div>
        {todo_stats.total > 0 && (
          <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-bg-elevated">
            {['done', 'active', 'error', 'pending'].map((status) => {
              const count = todo_stats[status as keyof typeof todo_stats];
              if (typeof count !== 'number' || count === 0) return null;
              const pct = (count / todo_stats.total) * 100;
              return (
                <div
                  key={status}
                  className={`${STATUS_COLORS[status] || 'bg-text-muted'} transition-all`}
                  style={{ width: `${pct}%` }}
                />
              );
            })}
          </div>
        )}
      </section>

      {/* Version Progress */}
      {version_progress.length > 0 && (
        <section>
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold text-text-primary">
            <GitBranch size={14} className="text-accent" /> 版本进度
          </h3>
          <div className="space-y-2.5">
            {version_progress.map((v) => (
              <div key={v.id} className="rounded-lg border border-border bg-bg-card p-3">
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-xs font-medium text-text-primary">{v.name}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    v.status === 'released' ? 'bg-status-done/15 text-status-done'
                    : v.status === 'active' ? 'bg-accent/15 text-accent'
                    : 'bg-text-muted/15 text-text-muted'
                  }`}>
                    {v.status === 'released' ? '已发布' : v.status === 'active' ? '进行中' : '规划中'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-elevated">
                    <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${v.progress}%` }} />
                  </div>
                  <span className="text-[10px] text-text-muted">{v.done}/{v.total}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Agent Stats */}
      {(agent_stats.completed > 0 || agent_stats.running > 0) && (
        <section>
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold text-text-primary">
            <Loader2 size={14} className="text-accent" /> Agent 执行
          </h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="等待中" value={agent_stats.pending} color="text-text-muted" />
            <StatCard label="执行中" value={agent_stats.running} color="text-accent" />
            <StatCard label="已完成" value={agent_stats.completed} color="text-status-done" />
            <StatCard label="失败" value={agent_stats.error} color="text-status-error" />
          </div>
        </section>
      )}

      {/* Recent Activity */}
      {recent_activity.length > 0 && (
        <section>
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold text-text-primary">
            <Clock size={14} className="text-accent" /> 最近更新
          </h3>
          <div className="space-y-1.5">
            {recent_activity.map((item) => (
              <div key={item.id} className="flex items-center gap-2.5 rounded-md px-3 py-2 hover:bg-bg-elevated">
                {item.status === 'done' ? (
                  <CheckCircle2 size={13} className="flex-shrink-0 text-status-done" />
                ) : item.status === 'error' ? (
                  <AlertCircle size={13} className="flex-shrink-0 text-status-error" />
                ) : (
                  <div className={`h-2 w-2 flex-shrink-0 rounded-full ${
                    item.status === 'active' ? 'bg-accent' : 'bg-text-muted'
                  }`} />
                )}
                <span className="min-w-0 flex-1 truncate text-xs text-text-primary">{item.title}</span>
                <span className="flex-shrink-0 text-[10px] text-text-muted">
                  {new Date(item.updated_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-3 text-center">
      <div className={`text-lg font-bold ${color}`}>{value}</div>
      <div className="text-[10px] text-text-muted">{label}</div>
    </div>
  );
}
