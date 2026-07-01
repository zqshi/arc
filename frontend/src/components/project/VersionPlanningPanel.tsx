import { useState, useCallback } from 'react';
import { api } from '../../api/client';
import { useToast } from '../Toast';
import { ConflictDetectionPanel } from './ConflictDetectionPanel';
import { ScopeDiffPreview, SessionCard } from './version-planning-panel-parts';
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

      {/* 冲突检测 */}
      <div className="rounded-lg border border-border bg-bg-card p-3">
        <ConflictDetectionPanel projectId={projectId} versionId={versionId} />
      </div>
    </div>
  );
}
