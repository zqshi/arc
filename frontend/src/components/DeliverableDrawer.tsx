import { useEffect, useRef } from 'react';
import { X, FileText, Code, TestTube, Rocket, BookOpen, Layout, Package } from 'lucide-react';
import MarkdownContent from './MarkdownContent';
import ArtifactRenderer from './artifact-renderers';
import type { Artifact, PlanningSession } from '../types/api';

type DrawerContent =
  | { type: 'artifact'; data: Artifact }
  | { type: 'roadmap'; data: PlanningSession };

interface DeliverableDrawerProps {
  open: boolean;
  onClose: () => void;
  content: DrawerContent | null;
}

const ARTIFACT_TYPE_ICONS: Record<string, typeof FileText> = {
  requirement_spec: FileText,
  ui_design: Layout,
  tech_architecture: Code,
  dev_report: Package,
  test_report: TestTube,
  deploy_report: Rocket,
  experience_card: BookOpen,
};

const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  requirement_spec: '需求规格',
  ui_design: 'UI 设计',
  tech_architecture: '技术架构',
  dev_report: '开发报告',
  test_report: '测试报告',
  deploy_report: '部署报告',
  experience_card: '经验卡片',
};

export default function DeliverableDrawer({ open, onClose, content }: DeliverableDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (open) document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [open, onClose]);

  if (!open || !content) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        ref={drawerRef}
        className="relative w-full max-w-2xl animate-slide-left overflow-hidden border-l border-border bg-bg-card shadow-2xl"
      >
        <div className="flex h-full flex-col">
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
            <button
              onClick={onClose}
              className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-elevated hover:text-text-secondary"
            >
              <X size={16} />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {content.type === 'artifact' ? (
              <ArtifactContent artifact={content.data} />
            ) : (
              <RoadmapContent session={content.data} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ArtifactContent({ artifact }: { artifact: Artifact }) {
  return <ArtifactRenderer artifactType={artifact.artifact_type} content={artifact.content || {}} />;
}

function RoadmapContent({ session }: { session: PlanningSession }) {
  const roadmap = session.roadmap || {};
  const versions = (roadmap as Record<string, unknown>).versions as Array<Record<string, unknown>> | undefined;
  const strategy = (roadmap as Record<string, unknown>).strategy as string | undefined;
  const strategyRationale = (roadmap as Record<string, unknown>).strategy_rationale as string | undefined;
  const totalWeeks = (roadmap as Record<string, unknown>).total_estimated_weeks as number | undefined;
  const timelineMermaid = (roadmap as Record<string, unknown>).timeline_mermaid as string | undefined;

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
              const features = v.features as Array<Record<string, unknown>> | undefined;
              const risks = v.risks as string[] | undefined;
              return (
                <div key={i} className="rounded-lg border border-border bg-bg-elevated p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-[9px] font-bold text-white">{i + 1}</span>
                    <span className="text-xs font-semibold text-text-primary">{v.name as string}</span>
                    {v.estimated_sprints && (
                      <span className="text-[10px] text-text-muted">{v.estimated_sprints as number} 个迭代</span>
                    )}
                  </div>
                  <p className="mb-2 text-[11px] text-text-secondary">{v.goal as string}</p>
                  {v.scope_rationale && (
                    <p className="mb-2 text-[10px] italic text-text-muted">{v.scope_rationale as string}</p>
                  )}
                  {features && features.length > 0 && (
                    <div className="mb-2 space-y-1">
                      {features.map((feat, fi) => (
                        <div key={fi} className="flex items-center gap-2 text-[11px]">
                          <span className="text-text-muted">-</span>
                          <span className="flex-1 text-text-primary">{feat.title as string}</span>
                          {feat.complexity && (
                            <span className="rounded bg-bg-card px-1.5 py-0.5 text-[9px] text-text-muted">{feat.complexity as string}</span>
                          )}
                          {feat.priority && (
                            <span className="text-[9px] text-text-muted">P{feat.priority as number}</span>
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


