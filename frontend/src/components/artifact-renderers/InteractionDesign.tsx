import { lazy, Suspense } from 'react';
import { GitBranch, Map, MousePointer, AlertTriangle, Layers } from 'lucide-react';
import { SectionCard } from './shared';
import { asArray } from './utils';

const MermaidDiagram = lazy(() => import('./MermaidDiagram'));

interface Props {
  content: Record<string, unknown>;
}

interface UserFlow {
  name?: string;
  description?: string;
  mermaid?: string;
}

interface PageMapItem {
  page?: string;
  entry_from?: string;
  exits_to?: string[];
  triggers?: string;
}

interface InteractionRule {
  component?: string;
  action?: string;
  response?: string;
  feedback?: string;
}

interface ErrorFlow {
  scenario?: string;
  handling?: string;
  user_message?: string;
}

interface StateDefinition {
  page?: string;
  states?: string[];
  transitions?: string;
}

export default function InteractionDesign({ content }: Props) {
  const userFlows = asArray(content.user_flows) as UserFlow[];
  const pageMap = asArray(content.page_map) as PageMapItem[];
  const interactionRules = asArray(content.interaction_rules) as InteractionRule[];
  const errorFlows = asArray(content.error_flows) as ErrorFlow[];
  const stateDefinitions = asArray(content.state_definitions) as StateDefinition[];

  return (
    <div>
      {userFlows.length > 0 && (
        <SectionCard icon={<GitBranch size={13} />} title="用户流程">
          <div className="space-y-4">
            {userFlows.map((flow, i) => (
              <div key={i}>
                <h5 className="mb-1 text-xs font-medium text-text-primary">{flow.name || `流程 ${i + 1}`}</h5>
                {flow.description && <p className="mb-2 text-[11px] text-text-secondary">{flow.description}</p>}
                {flow.mermaid && (
                  <Suspense fallback={<div className="h-32 animate-pulse rounded bg-bg-card" />}>
                    <MermaidDiagram code={flow.mermaid} />
                  </Suspense>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {pageMap.length > 0 && (
        <SectionCard icon={<Map size={13} />} title="页面地图">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/50 text-[10px] uppercase text-text-tertiary">
                  <th className="pb-1.5 pr-3 font-semibold">页面</th>
                  <th className="pb-1.5 pr-3 font-semibold">入口</th>
                  <th className="pb-1.5 pr-3 font-semibold">出口</th>
                  <th className="pb-1.5 font-semibold">触发条件</th>
                </tr>
              </thead>
              <tbody>
                {pageMap.map((item, i) => (
                  <tr key={i} className="border-b border-border/30 last:border-0">
                    <td className="py-1.5 pr-3 font-medium text-text-primary">{item.page}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{item.entry_from}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{item.exits_to?.join(', ')}</td>
                    <td className="py-1.5 text-text-muted text-[11px]">{item.triggers}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {interactionRules.length > 0 && (
        <SectionCard icon={<MousePointer size={13} />} title="交互规则">
          <div className="space-y-2">
            {interactionRules.map((rule, i) => (
              <div key={i} className="rounded-md border border-border/50 bg-bg-card p-2.5">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-medium text-text-primary">{rule.component}</span>
                  <span className="text-[10px] text-text-muted">→ {rule.action}</span>
                </div>
                <p className="mt-1 text-[11px] text-text-secondary">{rule.response}</p>
                {rule.feedback && <p className="mt-0.5 text-[10px] text-text-muted">反馈: {rule.feedback}</p>}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {errorFlows.length > 0 && (
        <SectionCard icon={<AlertTriangle size={13} />} title="异常流程">
          <div className="space-y-2">
            {errorFlows.map((ef, i) => (
              <div key={i} className="rounded-md border border-status-error/20 bg-status-error/5 p-2.5">
                <p className="text-[11px] font-medium text-text-primary">{ef.scenario}</p>
                <p className="mt-1 text-[11px] text-text-secondary">{ef.handling}</p>
                {ef.user_message && <p className="mt-0.5 text-[10px] italic text-text-muted">"{ef.user_message}"</p>}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {stateDefinitions.length > 0 && (
        <SectionCard icon={<Layers size={13} />} title="页面状态">
          <div className="space-y-2">
            {stateDefinitions.map((sd, i) => (
              <div key={i} className="rounded-md border border-border/50 bg-bg-card p-2.5">
                <p className="text-[11px] font-medium text-text-primary">{sd.page}</p>
                {sd.states && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {sd.states.map((s, si) => (
                      <span key={si} className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] text-text-secondary">{s}</span>
                    ))}
                  </div>
                )}
                {sd.transitions && <p className="mt-1 text-[10px] text-text-muted">{sd.transitions}</p>}
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
