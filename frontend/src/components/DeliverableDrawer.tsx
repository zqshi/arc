import { useEffect, useRef, useCallback, useState } from 'react';
import { X, FileText, Code, TestTube, Rocket, BookOpen, Layout, Package, Palette, Monitor, GitBranch, Pencil } from 'lucide-react';
import MarkdownContent from './MarkdownContent';
import ArtifactRenderer from './artifact-renderers';
import ArtifactEditor from './artifact/ArtifactEditor';
import { isArtifactEditable } from './artifact/editable-types';
import RollbackButton from './deployment/RollbackButton';
import type { Artifact, PlanningSession } from '../types/api';

type DrawerContent =
  | { type: 'artifact'; data: Artifact }
  | { type: 'roadmap'; data: PlanningSession };

interface DeliverableDrawerProps {
  onClose: () => void;
  content: DrawerContent | null;
  width: number;
  onWidthChange: (w: number) => void;
  /** v5.5.0: 传入 todoId 才会显示 artifact 编辑按钮 */
  todoId?: string;
  /** v5.5.0: 编辑成功后通知上层刷新 */
  onArtifactUpdated?: (updated: Artifact) => void;
  /** v5.5.0: 部署回滚所需 (deploy_report 类型时显示 RollbackButton) */
  projectId?: string;
  versionId?: string;
}

const MIN_WIDTH = 320;
const MAX_WIDTH = 720;

const ARTIFACT_TYPE_ICONS: Record<string, typeof FileText> = {
  requirement_spec: FileText,
  interaction_design: GitBranch,
  ui_spec: Palette,
  prototype: Monitor,
  tech_architecture: Code,
  dev_report: Package,
  test_report: TestTube,
  deploy_report: Rocket,
  experience_card: BookOpen,
  ui_design: Layout,
};

const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  requirement_spec: '需求规格',
  interaction_design: '交互设计',
  ui_spec: '视觉规范',
  prototype: '原型设计',
  tech_architecture: '技术架构',
  dev_report: '开发报告',
  test_report: '测试报告',
  deploy_report: '部署报告',
  experience_card: '经验卡片',
  ui_design: 'UI设计(旧)',
  app_code: '应用代码',
  service_spec: '服务契约',
};

export default function DeliverableDrawer({
  onClose,
  content,
  width,
  onWidthChange,
  todoId,
  onArtifactUpdated,
  projectId,
  versionId,
}: DeliverableDrawerProps) {
  const dragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);
  // v5.5.0: artifact 编辑模式 (仅 artifact 内容可切换)
  const [editMode, setEditMode] = useState(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  const onMouseMove = useCallback((e: MouseEvent) => {
    if (!dragging.current) return;
    const delta = startX.current - e.clientX;
    const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth.current + delta));
    onWidthChange(newWidth);
  }, [onWidthChange]);

  const onMouseUp = useCallback(() => {
    dragging.current = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startX.current = e.clientX;
    startWidth.current = width;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [width, onMouseMove, onMouseUp]);

  if (!content) return null;

  return (
    <div
      className="relative flex flex-shrink-0 animate-slide-left border-l border-border bg-bg-card"
      style={{ width }}
    >
      {/* Drag handle */}
      <div
        onMouseDown={onDragStart}
        className="absolute inset-y-0 left-0 z-10 w-1 cursor-col-resize transition-colors hover:bg-accent/40"
      />

      <div className="flex h-full flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            {content.type === 'artifact' ? (
              <>
                {(() => {
                  const Icon = ARTIFACT_TYPE_ICONS[content.data.artifact_type] || FileText;
                  return <Icon size={15} className="text-accent" />;
                })()}
                {ARTIFACT_TYPE_LABELS[content.data.artifact_type] || content.data.artifact_type}
              </>
            ) : (
              <>
                <Code size={15} className="text-accent" />
                版本路线图
              </>
            )}
          </h2>
          <div className="flex items-center gap-1">
            {/* v5.5.0: artifact 编辑入口 (仅可编辑类型 + 提供 todoId 时显示) */}
            {content.type === 'artifact'
              && todoId
              && isArtifactEditable(content.data.artifact_type)
              && !editMode && (
                <button
                  onClick={() => setEditMode(true)}
                  className="flex h-7 items-center gap-1 rounded-md px-2 text-text-muted transition-colors hover:bg-bg-elevated hover:text-accent"
                  aria-label="编辑产出物"
                  title="编辑产出物"
                >
                  <Pencil size={13} />
                  <span className="text-[11px]">编辑</span>
                </button>
              )}
            {/* v5.5.0: 部署回滚入口 (deploy_report 类型 + 有 projectId/versionId 时显示) */}
            {content.type === 'artifact'
              && content.data.artifact_type === 'deploy_report'
              && projectId
              && versionId && (
                <RollbackButton projectId={projectId} versionId={versionId} />
              )}
            <button
              onClick={onClose}
              className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-elevated hover:text-text-secondary"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Content */}
        {content.type === 'artifact' && editMode && todoId ? (
          <ArtifactEditor
            artifact={content.data}
            todoId={todoId}
            onSave={(updated) => {
              setEditMode(false);
              onArtifactUpdated?.(updated);
            }}
            onCancel={() => setEditMode(false)}
          />
        ) : (
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {content.type === 'artifact' ? (
              <ArtifactContent artifact={content.data} />
            ) : (
              <RoadmapContent session={content.data} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ArtifactContent({ artifact }: { artifact: Artifact }) {
  return <ArtifactRenderer artifactType={artifact.artifact_type} content={artifact.content ?? {}} />;
}

function RoadmapContent({ session }: { session: PlanningSession }) {
  const roadmap = session.roadmap || {};
  const { versions, strategy, strategy_rationale: strategyRationale, total_estimated_weeks: totalWeeks, timeline_mermaid: timelineMermaid } = roadmap;

  return (
    <div className="space-y-4">
      {strategy && (
        <div>
          <h3 className="mb-1 text-xs font-semibold text-text-tertiary uppercase tracking-wide">策略</h3>
          <p className="text-sm font-medium text-text-primary">{strategy}</p>
          {strategyRationale && <p className="mt-1 text-[11px] text-text-secondary">{strategyRationale}</p>}
          {totalWeeks && <p className="mt-1 text-[10px] text-text-muted">预估总工期: {totalWeeks} 周</p>}
        </div>
      )}

      {timelineMermaid && (
        <div>
          <h3 className="mb-2 text-xs font-semibold text-text-tertiary uppercase tracking-wide">时间线</h3>
          <div className="rounded-lg border border-border bg-bg-elevated p-4">
            <MarkdownContent content={`\`\`\`mermaid\n${timelineMermaid}\n\`\`\``} />
          </div>
        </div>
      )}

      {versions && versions.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold text-text-tertiary uppercase tracking-wide">版本计划</h3>
          <div className="space-y-3">
            {versions.map((v, i) => {
              const { features, risks } = v;
              return (
                <div key={i} className="rounded-lg border border-border bg-bg-elevated p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-[9px] font-bold text-white">{i + 1}</span>
                    <span className="text-xs font-semibold text-text-primary">{v.name}</span>
                    {v.estimated_sprints != null && (
                      <span className="text-[10px] text-text-muted">{String(v.estimated_sprints)} 个迭代</span>
                    )}
                  </div>
                  <p className="mb-2 text-[11px] text-text-secondary">{String(v.goal ?? '')}</p>
                  {v.scope_rationale != null && (
                    <p className="mb-2 text-[10px] italic text-text-muted">{String(v.scope_rationale)}</p>
                  )}
                  {features && features.length > 0 && (
                    <div className="mb-2 space-y-1">
                      {features.map((feat, fi) => (
                        <div key={fi} className="flex items-center gap-2 text-[11px]">
                          <span className="text-text-muted">-</span>
                          <span className="flex-1 text-text-primary">{feat.title}</span>
                          {feat.complexity != null && (
                            <span className="rounded bg-bg-card px-1.5 py-0.5 text-[9px] text-text-muted">{String(feat.complexity)}</span>
                          )}
                          {feat.priority != null && (
                            <span className="text-[9px] text-text-muted">P{String(feat.priority)}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {risks && risks.length > 0 && (
                    <div className="mt-2 rounded bg-status-error/5 px-2.5 py-1.5">
                      <p className="text-[10px] font-medium text-status-error">风险</p>
                      {risks.map((r, ri) => (
                        <p key={ri} className="text-[10px] text-text-secondary">- {r}</p>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
