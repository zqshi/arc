import { Server, Database, Globe, GitBranch, ListChecks } from 'lucide-react';
import { SectionCard, TextBlock, CodeBlock, asString, asArray } from './shared';

interface Props {
  content: Record<string, unknown>;
}

interface TechDecision {
  decision?: string;
  options?: string;
  chosen?: string;
  reason?: string;
}

export default function TechArchitecture({ content }: Props) {
  const overview = asString(content.architecture_overview);
  const dataModel = asString(content.data_model);
  const apiDesign = asString(content.api_design);
  const techDecisions = asArray(content.tech_decisions) as TechDecision[];
  const implementationPlan = asString(content.implementation_plan);

  return (
    <div>
      {overview && (
        <SectionCard icon={<Server size={13} />} title="架构概览">
          <TextBlock>{overview}</TextBlock>
        </SectionCard>
      )}

      {dataModel && (
        <SectionCard icon={<Database size={13} />} title="数据模型" variant="code">
          <CodeBlock>{dataModel}</CodeBlock>
        </SectionCard>
      )}

      {apiDesign && (
        <SectionCard icon={<Globe size={13} />} title="API 设计" variant="code">
          <CodeBlock>{apiDesign}</CodeBlock>
        </SectionCard>
      )}

      {techDecisions.length > 0 && (
        <SectionCard icon={<GitBranch size={13} />} title="技术决策">
          <div className="space-y-2.5">
            {techDecisions.map((d, i) => (
              <div key={i} className="rounded-md border border-border/50 bg-bg-card p-3">
                <p className="mb-1 text-xs font-medium text-text-primary">{d.decision}</p>
                {d.options && (
                  <p className="mb-1 text-[11px] text-text-muted">
                    考虑选项: {d.options}
                  </p>
                )}
                <div className="flex items-center gap-2">
                  <span className="rounded bg-status-done/15 px-1.5 py-0.5 text-[10px] font-medium text-status-done">
                    选择: {d.chosen}
                  </span>
                  {d.reason && (
                    <span className="text-[10px] text-text-secondary">— {d.reason}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {implementationPlan && (
        <SectionCard icon={<ListChecks size={13} />} title="实现计划">
          <TextBlock>{implementationPlan}</TextBlock>
        </SectionCard>
      )}
    </div>
  );
}
