import {
  Map, Check, Rocket, RefreshCw, Eye, Loader2,
} from 'lucide-react';
import MarkdownContent from '../MarkdownContent';
import type { PlanningSession } from '../../types/api';

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿', reviewing: '待确认', confirmed: '已确认', applied: '已应用',
};
const STATUS_COLOR: Record<string, string> = {
  draft: 'bg-text-muted/15 text-text-muted',
  reviewing: 'bg-amber-500/15 text-amber-500',
  confirmed: 'bg-accent/15 text-accent',
  applied: 'bg-status-done/15 text-status-done',
};

/** 单个路线图会话卡片 */
export function RoadmapCard({
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
  const { versions, strategy, strategy_rationale: strategyRationale, total_estimated_weeks: totalWeeks, timeline_mermaid: timelineMermaid } = roadmap;

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Map size={13} className="text-accent" />
          <span className="text-[11px] font-medium text-text-primary">{strategy || '版本路线图'}</span>
          <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${STATUS_COLOR[session.status] || ''}`}>
            {STATUS_LABEL[session.status] || session.status}
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
                <span className="text-[11px] font-medium text-text-primary">{v.name}</span>
                {v.estimated_sprints != null && <span className="text-[9px] text-text-muted">{String(v.estimated_sprints)} 个迭代</span>}
              </div>
              <p className="mb-1 text-[10px] text-text-secondary">{v.goal}</p>
              {v.features?.slice(0, 5).map((feat, fi) => (
                <div key={fi} className="flex items-center gap-2 pl-6 text-[10px] text-text-secondary">
                  <span className="text-text-muted">-</span>
                  <span>{feat.title}</span>
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
