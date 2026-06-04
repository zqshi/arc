import { Monitor, Layers, Navigation } from 'lucide-react';
import { SectionCard, TextBlock } from './shared';
import { asString, asArray } from './utils';
import InteractivePrototype from '../prototype/InteractivePrototype';
import type { SelectedElementInfo } from '../prototype/inspector';

interface Props {
  content: Record<string, unknown>;
  onElementSelected?: (info: SelectedElementInfo) => void;
  onRequestModify?: (info: SelectedElementInfo, instruction: string) => void;
}

interface Page {
  name?: string;
  description?: string;
  html?: string;
  responsive_notes?: string;
}

interface ComponentItem {
  name?: string;
  html?: string;
  props?: string;
}

export default function Prototype({ content, onElementSelected, onRequestModify }: Props) {
  const pages = asArray(content.pages) as Page[];
  const componentLibrary = asArray(content.component_library) as ComponentItem[];
  const navigation = asString(content.navigation);

  return (
    <div>
      {pages.length > 0 && (
        <SectionCard icon={<Monitor size={13} />} title="页面原型">
          <div className="space-y-4">
            {pages.map((page, i) => (
              <div key={i}>
                {page.html ? (
                  <InteractivePrototype
                    pageName={page.name || `页面 ${i + 1}`}
                    description={page.description}
                    html={page.html}
                    onElementSelected={onElementSelected}
                    onRequestModify={onRequestModify}
                  />
                ) : (
                  <div className="rounded-md border border-border/50 bg-bg-card p-3">
                    <h5 className="text-xs font-medium text-text-primary">{page.name || `页面 ${i + 1}`}</h5>
                    {page.description && <p className="mt-1 text-[11px] text-text-secondary">{page.description}</p>}
                  </div>
                )}
                {page.responsive_notes && (
                  <p className="mt-1 text-[10px] text-text-muted">响应式: {page.responsive_notes}</p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {componentLibrary.length > 0 && (
        <SectionCard icon={<Layers size={13} />} title="组件库">
          <div className="space-y-3">
            {componentLibrary.map((comp, i) => (
              <div key={i}>
                {comp.html ? (
                  <InteractivePrototype
                    pageName={comp.name || `组件 ${i + 1}`}
                    description={comp.props}
                    html={comp.html}
                    onElementSelected={onElementSelected}
                    onRequestModify={onRequestModify}
                  />
                ) : (
                  <div className="rounded-md border border-border/50 bg-bg-card p-2.5">
                    <p className="text-[11px] font-medium text-text-primary">{comp.name}</p>
                    {comp.props && <p className="mt-1 text-[10px] text-text-muted">{comp.props}</p>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {navigation && (
        <SectionCard icon={<Navigation size={13} />} title="导航结构">
          <TextBlock>{navigation}</TextBlock>
        </SectionCard>
      )}
    </div>
  );
}
