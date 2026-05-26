import { Palette, Grid3X3, Type, Layers, Sparkles } from 'lucide-react';
import { SectionCard, TextBlock } from './shared';
import { asString, asArray } from './utils';

interface Props {
  content: Record<string, unknown>;
}

interface ComponentSpec {
  name?: string;
  variants?: string[];
  states?: string[];
  sizing?: string;
  usage?: string;
}

export default function UISpec({ content }: Props) {
  const designTokens = content.design_tokens as Record<string, unknown> | undefined;
  const componentSpecs = asArray(content.component_specs) as ComponentSpec[];
  const layoutGrid = content.layout_grid as Record<string, unknown> | undefined;
  const iconography = asString(content.iconography);
  const motion = asString(content.motion);

  const colors = designTokens?.colors as Record<string, string> | undefined;
  const typography = designTokens?.typography as Record<string, unknown> | undefined;
  const spacing = designTokens?.spacing as Record<string, unknown> | undefined;

  return (
    <div>
      {colors && (
        <SectionCard icon={<Palette size={13} />} title="色彩体系">
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(colors).map(([name, value]) => (
              <div key={name} className="flex items-center gap-2">
                <div className="h-6 w-6 rounded border border-border/50" style={{ backgroundColor: value || '#ccc' }} />
                <div>
                  <p className="text-[10px] font-medium text-text-primary">{name}</p>
                  <p className="text-[9px] text-text-muted">{value}</p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {typography && (
        <SectionCard icon={<Type size={13} />} title="字体层级">
          <div className="space-y-2">
            {Object.entries(typography).map(([category, spec]) => {
              const s = spec as Record<string, string>;
              return (
                <div key={category} className="flex items-baseline gap-3 rounded-md border border-border/50 bg-bg-card p-2">
                  <span className="text-[11px] font-medium text-text-primary capitalize">{category}</span>
                  <span className="text-[10px] text-text-secondary">{s?.font}</span>
                  <span className="text-[10px] text-text-muted">{s?.sizes}</span>
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}

      {spacing && (
        <SectionCard icon={<Grid3X3 size={13} />} title="间距系统">
          <div className="flex flex-wrap gap-2">
            {((spacing.scale as number[]) || []).map((val) => (
              <div key={val} className="flex flex-col items-center gap-0.5">
                <div className="rounded bg-accent/20" style={{ width: val, height: val, minWidth: 8, minHeight: 8 }} />
                <span className="text-[9px] text-text-muted">{val}</span>
              </div>
            ))}
          </div>
          {spacing.unit != null && <p className="mt-2 text-[10px] text-text-muted">基础单位: {String(spacing.unit)}px</p>}
        </SectionCard>
      )}

      {componentSpecs.length > 0 && (
        <SectionCard icon={<Layers size={13} />} title="组件规范">
          <div className="space-y-2">
            {componentSpecs.map((spec, i) => (
              <div key={i} className="rounded-md border border-border/50 bg-bg-card p-2.5">
                <p className="text-[11px] font-medium text-text-primary">{spec.name}</p>
                {spec.variants && spec.variants.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {spec.variants.map((v, vi) => (
                      <span key={vi} className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">{v}</span>
                    ))}
                  </div>
                )}
                {spec.states && spec.states.length > 0 && (
                  <p className="mt-1 text-[10px] text-text-muted">状态: {spec.states.join(' · ')}</p>
                )}
                {spec.sizing && <p className="mt-0.5 text-[10px] text-text-muted">尺寸: {spec.sizing}</p>}
                {spec.usage && <p className="mt-0.5 text-[10px] text-text-secondary">{spec.usage}</p>}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {layoutGrid && (
        <SectionCard icon={<Grid3X3 size={13} />} title="布局栅格">
          <div className="space-y-1 text-[11px] text-text-secondary">
            {layoutGrid.columns != null && <p>列数: {String(layoutGrid.columns)}</p>}
            {layoutGrid.gutter != null && <p>间距: {String(layoutGrid.gutter)}</p>}
            {layoutGrid.breakpoints != null && (
              <div className="mt-1">
                {Object.entries(layoutGrid.breakpoints as Record<string, string>).map(([bp, val]) => (
                  <span key={bp} className="mr-3 text-[10px]"><b>{bp}</b>: {val}</span>
                ))}
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {iconography && (
        <SectionCard icon={<Sparkles size={13} />} title="图标风格">
          <TextBlock>{iconography}</TextBlock>
        </SectionCard>
      )}

      {motion && (
        <SectionCard icon={<Sparkles size={13} />} title="动效原则">
          <TextBlock>{motion}</TextBlock>
        </SectionCard>
      )}
    </div>
  );
}
