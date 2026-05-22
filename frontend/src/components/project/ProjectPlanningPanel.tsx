import { useState, useCallback, useRef } from 'react';
import {
  Upload,
  FileText,
  Trash2,
  Loader2,
  Sparkles,
  Map,
  Check,
  Rocket,
  RefreshCw,
  Eye,
  X,
} from 'lucide-react';
import { api } from '../../api/client';
import { useToast } from '../Toast';
import MarkdownContent from '../MarkdownContent';
import type { PlanningDocument, PlanningSession } from '../../types/api';

interface ProjectPlanningPanelProps {
  projectId: string;
  onRoadmapApplied: () => void;
  onClose: () => void;
  onPreviewRoadmap?: (session: PlanningSession) => void;
}

export function ProjectPlanningPanel({ projectId, onRoadmapApplied, onClose, onPreviewRoadmap }: ProjectPlanningPanelProps) {
  const { toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const [documents, setDocuments] = useState<PlanningDocument[]>([]);
  const [sessions, setSessions] = useState<PlanningSession[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const [teamCapacity, setTeamCapacity] = useState(3);
  const [iterationWeeks, setIterationWeeks] = useState(2);
  const [releaseStrategy, setReleaseStrategy] = useState('mvp');

  const [generating, setGenerating] = useState(false);
  const [applying, setApplying] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [docs, sess] = await Promise.all([
        api.listDocuments(projectId),
        api.listPlanningSessions(projectId),
      ]);
      setDocuments(docs);
      setSessions(sess.filter((s) => !s.version_id));
    } catch {
      toast('加载规划数据失败', 'error');
    } finally {
      setLoaded(true);
    }
  }, [projectId, toast]);

  if (!loaded) {
    fetchData();
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const doc = await api.uploadDocument(projectId, file);
      setDocuments((prev) => [...prev, doc]);
      toast(`文档「${doc.filename}」已上传`, 'success');
    } catch (err) {
      toast(`上传失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      await api.deleteDocument(projectId, docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch {
      toast('删除失败', 'error');
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const session = await api.createPlanningSession(projectId, {
        document_ids: documents.map((d) => d.id),
        constraints: {
          team_capacity: teamCapacity,
          iteration_weeks: iterationWeeks,
          release_strategy: releaseStrategy,
        },
      });
      const generated = await api.generateRoadmap(projectId, session.id);
      setSessions((prev) => [generated, ...prev]);
      toast('路线图已生成', 'success');
    } catch (err) {
      toast(`生成失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setGenerating(false);
    }
  };

  const handleConfirm = async (sessionId: string) => {
    try {
      const updated = await api.confirmRoadmap(projectId, sessionId);
      setSessions((prev) => prev.map((s) => (s.id === sessionId ? updated : s)));
      toast('路线图已确认', 'success');
    } catch {
      toast('确认失败', 'error');
    }
  };

  const handleApply = async (sessionId: string) => {
    setApplying(true);
    try {
      const result = await api.applyRoadmap(projectId, sessionId);
      toast(result.message, 'success');
      const updated = await api.listPlanningSessions(projectId);
      setSessions(updated.filter((s) => !s.version_id));
      onRoadmapApplied();
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

  if (!loaded) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 size={16} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="mb-4 rounded-lg border border-accent/30 bg-bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="flex items-center gap-2 text-xs font-semibold text-text-primary">
          <Sparkles size={13} className="text-accent" /> AI 全局规划
        </h3>
        <button onClick={onClose} className="rounded p-1 text-text-muted hover:bg-bg-elevated hover:text-text-secondary">
          <X size={14} />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Documents */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
              <FileText size={11} /> 需求文档
            </p>
            <label className={`flex cursor-pointer items-center gap-1 rounded-md bg-accent px-2 py-1 text-[10px] font-medium text-white hover:bg-accent-hover ${uploading ? 'opacity-50' : ''}`}>
              {uploading ? <Loader2 size={10} className="animate-spin" /> : <Upload size={10} />}
              上传
              <input ref={fileRef} type="file" className="hidden" accept=".pdf,.md,.txt,.docx" onChange={handleUpload} disabled={uploading} />
            </label>
          </div>
          {documents.length > 0 ? (
            <div className="space-y-1.5">
              {documents.map((doc) => (
                <div key={doc.id} className="flex items-center gap-2 rounded border border-border bg-bg-elevated px-3 py-2">
                  <FileText size={12} className="flex-shrink-0 text-accent" />
                  <span className="min-w-0 flex-1 truncate text-[11px] text-text-primary">{doc.filename}</span>
                  <span className="text-[9px] text-text-muted">{(doc.size / 1024).toFixed(1)}KB</span>
                  {doc.parsed_features && (
                    <span className="text-[9px] text-text-muted">{doc.parsed_features.length} 功能点</span>
                  )}
                  <button onClick={() => handleDeleteDoc(doc.id)} className="text-text-muted hover:text-status-error">
                    <Trash2 size={11} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[10px] text-text-muted">上传PRD文档，AI拆分为版本路线图</p>
          )}
        </div>

        {/* Constraints */}
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-[10px] text-text-muted">团队规模</label>
            <input type="number" min={1} max={50} value={teamCapacity}
              onChange={(e) => setTeamCapacity(Number(e.target.value))}
              className="h-8 w-20 rounded border border-border bg-bg-input px-2 text-xs text-text-primary focus:border-border-active focus:outline-none" />
          </div>
          <div>
            <label className="mb-1 block text-[10px] text-text-muted">迭代周期(周)</label>
            <input type="number" min={1} max={12} value={iterationWeeks}
              onChange={(e) => setIterationWeeks(Number(e.target.value))}
              className="h-8 w-20 rounded border border-border bg-bg-input px-2 text-xs text-text-primary focus:border-border-active focus:outline-none" />
          </div>
          <div>
            <label className="mb-1 block text-[10px] text-text-muted">发布策略</label>
            <select value={releaseStrategy} onChange={(e) => setReleaseStrategy(e.target.value)}
              className="h-8 rounded border border-border bg-bg-input px-2 text-xs text-text-primary focus:border-border-active focus:outline-none">
              <option value="mvp">MVP 优先</option>
              <option value="module">模块优先</option>
              <option value="risk">风险驱动</option>
            </select>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating || documents.length === 0}
            className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-2 text-[11px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {generating ? <Loader2 size={12} className="animate-spin" /> : <Map size={12} />}
            {generating ? '生成中...' : '生成版本路线图'}
          </button>
        </div>

        {/* Sessions */}
        {sessions.length > 0 && (
          <div className="space-y-3">
            {sessions.map((session) => (
              <RoadmapCard
                key={session.id}
                session={session}
                onConfirm={() => handleConfirm(session.id)}
                onApply={() => handleApply(session.id)}
                onRevise={() => handleRevise(session.id)}
                onPreview={onPreviewRoadmap ? () => onPreviewRoadmap(session) : undefined}
                applying={applying}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RoadmapCard({
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
  const strategy = (roadmap as Record<string, unknown>).strategy as string | undefined;
  const strategyRationale = (roadmap as Record<string, unknown>).strategy_rationale as string | undefined;
  const totalWeeks = (roadmap as Record<string, unknown>).total_estimated_weeks as number | undefined;
  const timelineMermaid = (roadmap as Record<string, unknown>).timeline_mermaid as string | undefined;

  const statusLabel: Record<string, string> = {
    draft: '草稿', reviewing: '待确认', confirmed: '已确认', applied: '已应用',
  };
  const statusColor: Record<string, string> = {
    draft: 'bg-text-muted/15 text-text-muted',
    reviewing: 'bg-amber-500/15 text-amber-500',
    confirmed: 'bg-accent/15 text-accent',
    applied: 'bg-status-done/15 text-status-done',
  };

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Map size={13} className="text-accent" />
          <span className="text-[11px] font-medium text-text-primary">{strategy || '版本路线图'}</span>
          <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${statusColor[session.status] || ''}`}>
            {statusLabel[session.status] || session.status}
          </span>
          {totalWeeks && <span className="text-[10px] text-text-muted">预估 {totalWeeks} 周</span>}
        </div>
        <div className="flex items-center gap-1.5">
          {onPreview && (
            <button onClick={onPreview} className="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-text-muted hover:bg-bg-elevated hover:text-text-secondary">
              <Eye size={10} /> 预览
            </button>
          )}
          {session.status === 'reviewing' && (
            <button onClick={onConfirm} className="flex items-center gap-1 rounded-md bg-accent px-2 py-1 text-[10px] font-medium text-white hover:bg-accent-hover">
              <Check size={11} /> 确认
            </button>
          )}
          {session.status === 'confirmed' && (
            <button onClick={onApply} disabled={applying} className="flex items-center gap-1 rounded-md bg-status-done px-2 py-1 text-[10px] font-medium text-white hover:opacity-90 disabled:opacity-50">
              {applying ? <Loader2 size={11} className="animate-spin" /> : <Rocket size={11} />}
              应用到项目
            </button>
          )}
          {session.status === 'applied' && (
            <button onClick={onRevise} className="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-text-muted hover:bg-bg-elevated hover:text-text-secondary">
              <RefreshCw size={10} /> 重新规划
            </button>
          )}
        </div>
      </div>

      {strategyRationale && (
        <div className="border-t border-border/50 px-3 py-2">
          <p className="text-[10px] text-text-secondary">{strategyRationale}</p>
        </div>
      )}

      {versions && versions.length > 0 && (
        <div className="border-t border-border/50 px-3 py-2.5 space-y-2">
          {versions.map((v, i) => (
            <div key={i} className="rounded border border-border bg-bg-card p-2.5">
              <div className="mb-1 flex items-center gap-2">
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-accent text-[8px] font-bold text-white">{i + 1}</span>
                <span className="text-[11px] font-medium text-text-primary">{v.name as string}</span>
                {v.estimated_sprints && <span className="text-[9px] text-text-muted">{v.estimated_sprints as number} 个迭代</span>}
              </div>
              <p className="mb-1 text-[10px] text-text-secondary">{v.goal as string}</p>
              {(v.features as Array<Record<string, unknown>> | undefined)?.slice(0, 5).map((feat, fi) => (
                <div key={fi} className="flex items-center gap-2 pl-6 text-[10px] text-text-secondary">
                  <span className="text-text-muted">-</span>
                  <span>{feat.title as string}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {timelineMermaid && (
        <div className="border-t border-border/50 px-3 py-2">
          <div className="rounded bg-bg-card p-2">
            <MarkdownContent content={`\`\`\`mermaid\n${timelineMermaid}\n\`\`\``} />
          </div>
        </div>
      )}
    </div>
  );
}
