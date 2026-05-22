import { lazy, Suspense } from 'react';
import { GitBranch, Layout, Component, MousePointer, Smartphone } from 'lucide-react';
import { SectionCard, TextBlock } from './shared';
import { asString, asArray } from './utils';
import WireframePreview from './WireframePreview';

const MermaidDiagram = lazy(() => import('./MermaidDiagram'));

interface Props {
  content: Record<string, unknown>;
}

interface Wireframe {
  page_name?: string;
  description?: string;
  html?: string;
}

interface ComponentSpec {
  name?: string;
  purpose?: string;
  behavior?: string;
  states?: string;
}

export default function UIDesign({ content }: Props) {
  const flowDiagram = asString(content.flow_diagram);
  const wireframes = asArray(content.wireframes) as Wireframe[];
  const componentSpecs = asArray(content.component_specs) as ComponentSpec[];
  const interactionRules = asString(content.interaction_rules);
  const responsiveNotes = asString(content.responsive_notes);

  // backward compat: old format had user_flow + page_layouts
  const legacyUserFlow = asString(content.user_flow);

  return (
    <div>
      {(flowDiagram || legacyUserFlow) && (
        <SectionCard icon={<GitBranch size={13} />} title="用户流程">
          {flowDiagram ? (
            <Suspense fallback={<div className="h-32 animate-pulse rounded bg-bg-card" />}>
              <MermaidDiagram code={flowDiagram} />
            </Suspense>
          ) : (
            <TextBlock>{legacyUserFlow}</TextBlock>
          )}
        </SectionCard>
      )}

      {wireframes.length > 0 && (
        <SectionCard icon={<Layout size={13} />} title="页面线框">
          <div className="space-y-3">
            {wireframes.map((wf, i) => (
              wf.html ? (
                <WireframePreview
                  key={i}
                  pageName={wf.page_name || `页面 ${i + 1}`}
                  description={wf.description}
                  html={wf.html}
                />
              ) : (
                <div key={i} className="rounded-md border border-border/50 bg-bg-card p-3">
                  <h5 className="text-xs font-medium text-text-primary">
                    {wf.page_name || `页面 ${i + 1}`}
                  </h5>
                  {wf.description && (
                    <p className="mt-1 text-[11px] text-text-secondary">{wf.description}</p>
                  )}
                </div>
              )
            ))}
          </div>
        </SectionCard>
      )}

      {componentSpecs.length > 0 && (
        <SectionCard icon={<Component size={13} />} title="组件规格">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/50 text-[10px] uppercase text-text-tertiary">
                  <th className="pb-1.5 pr-3 font-semibold">组件</th>
                  <th className="pb-1.5 pr-3 font-semibold">用途</th>
                  <th className="pb-1.5 pr-3 font-semibold">交互</th>
                  <th className="pb-1.5 font-semibold">状态</th>
                </tr>
              </thead>
              <tbody>
                {componentSpecs.map((spec, i) => (
                  <tr key={i} className="border-b border-border/30 last:border-0">
                    <td className="py-1.5 pr-3 font-medium text-text-primary">{spec.name}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{spec.purpose}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{spec.behavior}</td>
                    <td className="py-1.5 text-text-muted text-[11px]">{spec.states}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {interactionRules && (
        <SectionCard icon={<MousePointer size={13} />} title="交互规则">
          <TextBlock>{interactionRules}</TextBlock>
        </SectionCard>
      )}

      {responsiveNotes && (
        <SectionCard icon={<Smartphone size={13} />} title="响应式说明">
          <TextBlock>{responsiveNotes}</TextBlock>
        </SectionCard>
      )}
    </div>
  );
}
