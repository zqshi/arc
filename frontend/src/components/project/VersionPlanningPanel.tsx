import { useState, useCallback } from 'react';
import {
  Loader2,
  Map,
  Check,
  Rocket,
  RefreshCw,
  Eye,
  AlertTriangle,
  Plus,
  Minus,
  X,
} from 'lucide-react';
import { api } from '../../api/client';
import { useToast } from '../Toast';
import type { PlanningSession, ScopeDiff } from '../../types/api';

interface VersionPlanningPanelProps {
  projectId: string;
  versionId: string;
  onTodosCreated: () => void;
  onPreviewRoadmap?: (session: PlanningSession) => void;
}

export function VersionPlanningPanel({ projectId, versionId, onTodosCreated, onPreviewRoadmap }: VersionPlanningPanelProps) {
  const { toast } = useToast();

  const [sessions, setSessions] = useState<PlanningSession[]>([]);
  const [loaded, setLoaded] = useState(false);

  const [applying, setApplying] = useState(false);
  const [scopeDiff, setScopeDiff] = useState<ScopeDiff | null>(null);
  const [diffSessionId, setDiffSessionId] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const sess = await api.listVersionPlanningSessions(projectId, versionId);
      setSessions(sess);
    } catch {
      toast('加载规划数据失败', 'error');
    } finally {
      setLoaded(true);
    }
  }, [projectId, versionId, toast]);

  if (!loaded) {
    fetchData();
  }

  const handleConfirm = async (sessionId: string) => {
    try {
      const updated = await api.confirmRoadmap(projectId, sessionId);
      setSessions((prev) => prev.map((s) => (s.id === sessionId ? updated : s)));
      toast('已确认', 'success');
    } catch {
      toast('确认失败', 'error');
    }
  };

  const handleApply = async (sessionId: string) => {
    setApplying(true);
    try {
      const diff = await api.previewApplyDiff(projectId, sessionId);
      if (diff.is_first_apply) {
        const result = await api.applyRoadmap(projectId, sessionId);
        toast(result.message, 'success');
        const updated = await api.listVersionPlanningSessions(projectId, versionId);
        setSessions(updated);
        onTodosCreated();
      } else {
        setScopeDiff(diff);
        setDiffSessionId(sessionId);
      }
    } catch (err) {
      toast(`应用失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setApplying(false);
    }
  };

  const handleApplyWithDiff = async (abandonIds: string[]) => {
    if (!diffSessionId) return;
    setApplying(true);
    try {
      const result = await api.applyWithDiff(projectId, diffSessionId, abandonIds);
      toast(result.message, 'success');
      setScopeDiff(null);
      setDiffSessionId(null);
      const updated = await api.listVersionPlanningSessions(projectId, versionId);
      setSessions(updated);
      onTodosCreated();
    } catch (err) {
      toast(`应用失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setApplying(false);
    }
  };

  const handleRevise = async (sessionId: string) => {
    try {
      const updated = await api.revisePlanningSession(projectId, sessionId);
      setSessions((prev) => prev.map((s) => (s.id === sessionId ? updated : s)));
      toast('已回到草稿，可重新生成', 'success');
    } catch {
      toast('操作失败', 'error');
    }
  };

  const latestSession = sessions[0];

  return (
    <div className={latestSession || scopeDiff ? 'space-y-3 px-4 py-3' : ''}>
      {/* Session result */}
      {latestSession && (
        <SessionCard
          session={latestSession}
          onConfirm={() => handleConfirm(latestSession.id)}
          onApply={() => handleApply(latestSession.id)}
          onRevise={() => handleRevise(latestSession.id)}
          onPreview={onPreviewRoadmap ? () => onPreviewRoadmap(latestSession) : undefined}
          applying={applying}
        />
      )}

      {scopeDiff && (
        <ScopeDiffPreview
          diff={scopeDiff}
          applying={applying}
          onConfirm={handleApplyWithDiff}
          onCancel={() => { setScopeDiff(null); setDiffSessionId(null); }}
        />
      )}
    </div>
  );
}

function ScopeDiffPreview({
  diff,
  applying,
  onConfirm,
  onCancel,
}: {
  diff: ScopeDiff;
  applying: boolean;
  onConfirm: (abandonIds: string[]) => void;
  onCancel: () => void;
}) {
  const [abandonSet, setAbandonSet] = useState<Set<string>>(() => {
    const ids = new Set<string>();
    diff.removed_pending?.forEach((t) => ids.add(t.id));
    return ids;
  });

  const toggle = (id: string) => {
    setAbandonSet((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
      <div className="flex items-center gap-2 text-[11px] font-medium text-amber-600">
        <AlertTriangle size={13} /> 范围变更预览
      </div>

      {diff.added && diff.added.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-status-done mb-1">+ 新增 {diff.added.length} 项</p>
          <div className="space-y-0.5">
            {diff.added.map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] text-text-secondary">
                <Plus size={10} className="text-status-done" />
                <span className="flex-1 truncate">{f.title}</span>
                {f.complexity && <span className="text-[9px] text-text-muted">{f.complexity}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {diff.removed_active && diff.removed_active.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-amber-600 mb-1">
            <AlertTriangle size={10} className="inline" /> 进行中被移除 {diff.removed_active.length} 项（需确认）
          </p>
          <div className="space-y-1">
            {diff.removed_active.map((t) => (
              <div key={t.id} className="flex items-center gap-2 text-[11px]">
                <Minus size={10} className="text-amber-500" />
                <span className="flex-1 truncate text-text-secondary">{t.title}</span>
                <button
                  onClick={() => toggle(t.id)}
                  className={`rounded px-1.5 py-0.5 text-[9px] font-medium transition-colors ${
                    abandonSet.has(t.id)
                      ? 'bg-status-error/15 text-status-error'
                      : 'bg-status-done/15 text-status-done'
                  }`}
                >
                  {abandonSet.has(t.id) ? '废弃' : '保留'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {diff.removed_pending && diff.removed_pending.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-text-muted mb-1">
            待启动被移除 {diff.removed_pending.length} 项（默认废弃）
          </p>
          <div className="space-y-1">
            {diff.removed_pending.map((t) => (
              <div key={t.id} className="flex items-center gap-2 text-[11px]">
                <Minus size={10} className="text-text-muted" />
                <span className="flex-1 truncate text-text-muted">{t.title}</span>
                <button
                  onClick={() => toggle(t.id)}
                  className={`rounded px-1.5 py-0.5 text-[9px] font-medium transition-colors ${
                    abandonSet.has(t.id)
                      ? 'bg-status-error/15 text-status-error'
                      : 'bg-status-done/15 text-status-done'
                  }`}
                >
                  {abandonSet.has(t.id) ? '废弃' : '保留'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {diff.removed_done && diff.removed_done.length > 0 && (
        <p className="text-[10px] text-text-muted">
          已完成 {diff.removed_done.length} 项不再出现在新规划中（不受影响）
        </p>
      )}

      {diff.unchanged_count !== undefined && diff.unchanged_count > 0 && (
        <p className="text-[10px] text-text-muted">{diff.unchanged_count} 项未变更</p>
      )}

      <div className="flex items-center justify-end gap-2 pt-1">
        <button onClick={onCancel} className="rounded-md border border-border px-3 py-1 text-[10px] text-text-secondary hover:text-text-primary">
          <X size={10} className="inline mr-1" />取消
        </button>
        <button
          onClick={() => onConfirm(Array.from(abandonSet))}
          disabled={applying}
          className="flex items-center gap-1 rounded-md bg-accent px-3 py-1 text-[10px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {applying ? <Loader2 size={10} className="animate-spin" /> : <Check size={10} />}
          确认应用
        </button>
      </div>
    </div>
  );
}

function SessionCard({
  session,
  onConfirm,
  onApply,
  onRevise,
  onPreview,
  applying,
}: {
  session: PlanningSession;
  onConfirm: () => void;
  onApply: () => void;
  onRevise: () => void;
  onPreview?: () => void;
  applying: boolean;
}) {
  const roadmap = session.roadmap || {};
  const versions = (roadmap as Record<string, unknown>).versions as Array<Record<string, unknown>> | undefined;
  const features = versions?.flatMap((v) => (v.features as Array<Record<string, unknown>> | undefined) || []) || [];

  const statusLabel: Record<string, string> = {
    draft: '草稿',
    reviewing: '待确认',
    confirmed: '已确认',
    applied: '已应用',
  };
  const statusColor: Record<string, string> = {
    draft: 'bg-text-muted/15 text-text-muted',
    reviewing: 'bg-amber-500/15 text-amber-500',
    confirmed: 'bg-accent/15 text-accent',
    applied: 'bg-status-done/15 text-status-done',
  };

  return (
    <div className="rounded-md border border-border bg-bg-elevated">
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-2">
          <Map size={12} className="text-accent" />
          <span className="text-[11px] font-medium text-text-primary">
            AI 生成 · {features.length} 个需求
          </span>
          <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${statusColor[session.status] || ''}`}>
            {statusLabel[session.status] || session.status}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {onPreview && (
            <button onClick={onPreview} className="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-text-muted hover:bg-bg-card hover:text-text-secondary">
              <Eye size={10} /> 预览
            </button>
          )}
          {session.status === 'reviewing' && (
            <button onClick={onConfirm} className="flex items-center gap-1 rounded-md bg-accent px-2 py-1 text-[10px] font-medium text-white hover:bg-accent-hover">
              <Check size={10} /> 确认
            </button>
          )}
          {session.status === 'confirmed' && (
            <button onClick={onApply} disabled={applying} className="flex items-center gap-1 rounded-md bg-status-done px-2 py-1 text-[10px] font-medium text-white hover:opacity-90 disabled:opacity-50">
              {applying ? <Loader2 size={10} className="animate-spin" /> : <Rocket size={10} />}
              应用
            </button>
          )}
          {session.status === 'applied' && (
            <button onClick={onRevise} className="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-text-muted hover:bg-bg-card hover:text-text-secondary">
              <RefreshCw size={10} /> 重新规划
            </button>
          )}
        </div>
      </div>
      {features.length > 0 && (
        <div className="border-t border-border/50 px-3 py-2 space-y-1">
          {features.slice(0, 8).map((feat, i) => (
            <div key={i} className="flex items-center gap-2 text-[11px] text-text-secondary">
              <span className="text-text-muted">-</span>
              <span className="flex-1 truncate">{feat.title as string}</span>
              {feat.complexity && (
                <span className="rounded bg-bg-card px-1 py-0.5 text-[9px] text-text-muted">{feat.complexity as string}</span>
              )}
            </div>
          ))}
          {features.length > 8 && (
            <p className="text-[10px] text-text-muted pl-4">...还有 {features.length - 8} 个</p>
          )}
        </div>
      )}
    </div>
  );
}
