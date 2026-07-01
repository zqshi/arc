import type { DomainModelSubdomain } from '../../types/api';

const AGG_COLOR = { accent: '#2ecf9c', border: '#2ecf9c' };

/** 战略视图层: 子域 → 限界上下文 */
export function StrategicLayer({
  subdomain,
  contexts,
  color,
  onHover,
  onClick,
  selected,
}: {
  subdomain: DomainModelSubdomain;
  contexts: { name: string; description: string; team?: string }[];
  color: { accent: string; border: string };
  onHover: (id: string | null) => void;
  onClick: (id: string) => void;
  selected: string | null;
}) {
  return (
    <div className="relative z-[1] rounded-lg border border-border bg-bg-card p-3.5" style={{ borderLeftWidth: 3, borderLeftColor: color.border }}>
      <div className="mb-2 flex items-center gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-secondary">{subdomain.name}</h4>
        <span className="rounded-full bg-bg-elevated px-2 py-0.5 text-[9px] text-text-muted">{subdomain.type}</span>
      </div>
      {subdomain.description && <p className="mb-2 text-[10px] text-text-muted">{subdomain.description}</p>}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-2.5">
        {contexts.map((ctx) => {
          const nodeId = `ctx_${ctx.name}`;
          const isSelected = selected === nodeId;
          return (
            <div
              key={ctx.name}
              data-node-id={nodeId}
              className={`relative z-[3] cursor-pointer rounded-lg border bg-bg-elevated p-3 transition-all hover:-translate-y-px hover:border-accent/30 ${
                isSelected ? 'border-accent/50 shadow-[0_0_0_2px_rgba(46,207,156,0.18)]' : 'border-border'
              }`}
              onMouseEnter={() => onHover(nodeId)}
              onMouseLeave={() => onHover(null)}
              onClick={() => onClick(nodeId)}
            >
              <span
                className="absolute right-2 top-2 rounded-full px-1.5 py-0.5 text-[9px] font-bold"
                style={{ background: `${color.accent}20`, color: color.accent, border: `1px solid ${color.accent}50` }}
              >
                {subdomain.type}
              </span>
              <h5 className="pr-14 text-xs font-semibold text-text-primary">{ctx.name}</h5>
              <p className="mt-1 text-[10px] text-text-muted">{ctx.description || '限界上下文'}</p>
              {ctx.team && <p className="mt-1.5 text-[9px] text-text-muted">👥 {ctx.team}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 战术视图层: 限界上下文 → 聚合 */
export function TacticalLayer({
  context,
  aggregates,
  onHover,
  onClick,
  selected,
}: {
  context: { name: string; description: string; subdomain: string };
  aggregates: { name: string; description: string; entities: string[]; value_objects: string[]; events: string[]; methods: string[] }[];
  onHover: (id: string | null) => void;
  onClick: (id: string) => void;
  selected: string | null;
}) {
  return (
    <div className="relative z-[1] rounded-lg border border-border bg-bg-card p-3.5" style={{ borderLeftWidth: 3, borderLeftColor: AGG_COLOR.border }}>
      <div className="mb-2 flex items-center gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-secondary">{context.name}</h4>
        <span className="rounded-full bg-bg-elevated px-2 py-0.5 text-[9px] text-text-muted">限界上下文</span>
      </div>
      {context.description && <p className="mb-2 text-[10px] text-text-muted">{context.description}</p>}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-2.5">
        {aggregates.map((agg) => {
          const nodeId = `agg_${agg.name}`;
          const isSelected = selected === nodeId;
          return (
            <div
              key={agg.name}
              data-node-id={nodeId}
              className={`relative z-[3] cursor-pointer rounded-lg border bg-bg-elevated p-3 transition-all hover:-translate-y-px hover:border-accent/30 ${
                isSelected ? 'border-accent/50 shadow-[0_0_0_2px_rgba(46,207,156,0.18)]' : 'border-border'
              }`}
              onMouseEnter={() => onHover(nodeId)}
              onMouseLeave={() => onHover(null)}
              onClick={() => onClick(nodeId)}
            >
              <span className="absolute right-2 top-2 rounded-full border border-accent/50 bg-accent/15 px-1.5 py-0.5 text-[9px] font-bold text-accent">
                聚合
              </span>
              <h5 className="pr-10 text-xs font-semibold text-text-primary">{agg.name}</h5>
              <p className="mt-1 text-[10px] text-text-muted">{agg.description || '聚合根'}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {agg.entities.slice(0, 4).map((e) => (
                  <span key={e} className="rounded bg-blue-500/10 px-1.5 py-0.5 text-[9px] text-blue-500">{e}</span>
                ))}
                {agg.value_objects.slice(0, 3).map((v) => (
                  <span key={v} className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[9px] text-emerald-500">{v}</span>
                ))}
              </div>
              {agg.methods.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {agg.methods.slice(0, 3).map((m) => (
                    <span key={m} className="rounded border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[9px] text-accent">{m}</span>
                  ))}
                  {agg.methods.length > 3 && (
                    <span className="text-[9px] text-text-muted">+{agg.methods.length - 3}</span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
