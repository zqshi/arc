import { useState } from 'react';
import { Boxes, Layers, Network, Database, Zap, Circle } from 'lucide-react';
import type { DomainModel, DomainModelAggregate, DomainModelSubdomain } from '../../types/api';

type ViewMode = 'strategic' | 'tactical' | 'all';

const SUBDOMAIN_STYLES: Record<string, { border: string; bg: string; dot: string }> = {
  '核心域': { border: 'border-accent/40', bg: 'bg-accent/5', dot: 'bg-accent' },
  '支撑域': { border: 'border-blue-400/40', bg: 'bg-blue-400/5', dot: 'bg-blue-400' },
  '通用域': { border: 'border-amber-400/40', bg: 'bg-amber-400/5', dot: 'bg-amber-400' },
};

interface DomainModelTabProps {
  domainModel: DomainModel | null;
  loading: boolean;
}

export function DomainModelTab({ domainModel, loading }: DomainModelTabProps) {
  const [view, setView] = useState<ViewMode>('all');

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  if (!domainModel || isModelEmpty(domainModel)) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Boxes size={32} className="mb-3 text-text-muted/30" />
        <p className="text-sm font-medium text-text-secondary">暂无领域模型</p>
        <p className="mt-1 max-w-sm text-xs text-text-muted">
          在对话中产出「技术架构」交付物后，系统将自动提取数据模型并沉淀到此处。
          随着需求迭代，领域模型会持续累积完善。
        </p>
      </div>
    );
  }

  const views: { key: ViewMode; label: string }[] = [
    { key: 'strategic', label: '战略' },
    { key: 'tactical', label: '战术' },
    { key: 'all', label: '全部' },
  ];

  return (
    <div>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Boxes size={15} className="text-accent" />
          <h3 className="text-sm font-semibold text-text-primary">领域模型</h3>
          {domainModel.version && (
            <span className="rounded-full bg-bg-elevated px-2 py-0.5 text-[10px] text-text-muted">
              v{domainModel.version}
            </span>
          )}
        </div>
        <div className="flex rounded-full border border-border bg-bg-elevated p-0.5">
          {views.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
                view === key ? 'bg-accent/10 text-accent' : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="mb-4 flex gap-3">
        <StatPill icon={<Layers size={11} />} label="子域" count={domainModel.subdomains.length} />
        <StatPill icon={<Network size={11} />} label="上下文" count={domainModel.contexts.length} />
        <StatPill icon={<Database size={11} />} label="聚合" count={domainModel.aggregates.length} />
        <StatPill icon={<Zap size={11} />} label="关系" count={domainModel.relations.length + (domainModel.aggregate_relations?.length || 0)} />
      </div>

      {/* Strategic View */}
      {(view === 'strategic' || view === 'all') && domainModel.subdomains.length > 0 && (
        <section className="mb-5">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">子域划分</h4>
          <div className="grid gap-2">
            {domainModel.subdomains.map((sd) => (
              <SubdomainCard key={sd.name} subdomain={sd} contexts={domainModel.contexts.filter(c => c.subdomain === sd.name)} />
            ))}
          </div>
        </section>
      )}

      {/* Context Relations */}
      {(view === 'strategic' || view === 'all') && domainModel.relations.length > 0 && (
        <section className="mb-5">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">上下文关系</h4>
          <div className="space-y-1.5">
            {domainModel.relations.map((rel, i) => (
              <div key={i} className="flex items-center gap-2 rounded-md border border-border bg-bg-elevated px-3 py-2 text-[11px]">
                <span className="font-medium text-text-primary">{rel.from}</span>
                <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent">{rel.type}</span>
                <span className="text-text-muted">→</span>
                <span className="font-medium text-text-primary">{rel.to}</span>
                {rel.description && <span className="ml-auto text-text-muted">{rel.description}</span>}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Tactical View: Aggregates */}
      {(view === 'tactical' || view === 'all') && domainModel.aggregates.length > 0 && (
        <section className="mb-5">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">聚合模型</h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {domainModel.aggregates.map((agg) => (
              <AggregateCard key={agg.name} aggregate={agg} />
            ))}
          </div>
        </section>
      )}

      {/* Aggregate Relations */}
      {(view === 'tactical' || view === 'all') && domainModel.aggregate_relations && domainModel.aggregate_relations.length > 0 && (
        <section className="mb-5">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">聚合间引用</h4>
          <div className="space-y-1.5">
            {domainModel.aggregate_relations.map((rel, i) => (
              <div key={i} className="flex items-center gap-2 rounded-md border border-border bg-bg-elevated px-3 py-2 text-[11px]">
                <span className="font-medium text-text-primary">{rel.from}</span>
                <span className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] font-medium text-purple-500">{rel.type}</span>
                <span className="text-text-muted">→</span>
                <span className="font-medium text-text-primary">{rel.to}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Updated timestamp */}
      {domainModel.updated_at && (
        <p className="mt-4 text-[10px] text-text-muted">
          最后更新: {new Date(domainModel.updated_at).toLocaleString('zh-CN')}
        </p>
      )}
    </div>
  );
}

function StatPill({ icon, label, count }: { icon: React.ReactNode; label: string; count: number }) {
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-border bg-bg-elevated px-2.5 py-1">
      {icon}
      <span className="text-[10px] text-text-muted">{label}</span>
      <span className="text-[11px] font-semibold text-text-primary">{count}</span>
    </div>
  );
}

function SubdomainCard({ subdomain, contexts }: { subdomain: DomainModelSubdomain; contexts: { name: string; description: string }[] }) {
  const style = SUBDOMAIN_STYLES[subdomain.type] || SUBDOMAIN_STYLES['通用域'];
  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} p-3`}>
      <div className="flex items-center gap-2">
        <Circle size={8} className={`fill-current ${style.dot.replace('bg-', 'text-')}`} />
        <span className="text-xs font-semibold text-text-primary">{subdomain.name}</span>
        <span className="rounded-full bg-bg-elevated px-1.5 py-0.5 text-[9px] text-text-muted">{subdomain.type}</span>
      </div>
      {subdomain.description && (
        <p className="mt-1 pl-4 text-[11px] text-text-secondary">{subdomain.description}</p>
      )}
      {contexts.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5 pl-4">
          {contexts.map(ctx => (
            <span key={ctx.name} className="rounded-md border border-border/50 bg-bg-card px-2 py-0.5 text-[10px] text-text-secondary">
              {ctx.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function AggregateCard({ aggregate }: { aggregate: DomainModelAggregate }) {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Database size={12} className="text-accent" />
          <span className="text-xs font-semibold text-text-primary">{aggregate.name}</span>
        </div>
        {aggregate.context && (
          <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[9px] text-text-muted">{aggregate.context}</span>
        )}
      </div>
      {aggregate.description && (
        <p className="mt-1 text-[10px] text-text-muted">{aggregate.description}</p>
      )}
      <div className="mt-2 space-y-1">
        {aggregate.entities.length > 0 && (
          <TagRow label="实体" items={aggregate.entities} color="text-blue-500 bg-blue-500/10" />
        )}
        {aggregate.value_objects.length > 0 && (
          <TagRow label="值对象" items={aggregate.value_objects} color="text-emerald-500 bg-emerald-500/10" />
        )}
        {aggregate.fields && aggregate.fields.length > 0 && (
          <TagRow label="字段" items={aggregate.fields} color="text-text-muted bg-bg-elevated" />
        )}
        {aggregate.events.length > 0 && (
          <TagRow label="事件" items={aggregate.events} color="text-amber-500 bg-amber-500/10" />
        )}
        {aggregate.methods.length > 0 && (
          <TagRow label="方法" items={aggregate.methods} color="text-purple-500 bg-purple-500/10" />
        )}
      </div>
      {aggregate.source && (
        <p className="mt-2 text-[9px] text-text-muted">来源: {aggregate.source}</p>
      )}
    </div>
  );
}

function TagRow({ label, items, color }: { label: string; items: string[]; color: string }) {
  return (
    <div className="flex items-start gap-1.5">
      <span className="mt-0.5 w-8 flex-shrink-0 text-[9px] text-text-muted">{label}</span>
      <div className="flex flex-wrap gap-1">
        {items.map((item, i) => (
          <span key={i} className={`rounded px-1.5 py-0.5 text-[10px] ${color}`}>{item}</span>
        ))}
      </div>
    </div>
  );
}

function isModelEmpty(dm: DomainModel): boolean {
  return (
    dm.subdomains.length === 0 &&
    dm.contexts.length === 0 &&
    dm.aggregates.length === 0 &&
    dm.relations.length === 0
  );
}
