import type { ReactNode } from 'react';
import { Circle, Database, Loader2, ShieldCheck, CheckCircle2, AlertTriangle } from 'lucide-react';
import type { DomainModel, DomainModelAggregate, DomainModelSubdomain, BaasStatus } from '../../types/api';
import type { useDomainModelReview } from '../../hooks/useDomainModelReview';

export const SUBDOMAIN_STYLES: Record<string, { border: string; bg: string; dot: string }> = {
  '核心域': { border: 'border-accent/40', bg: 'bg-accent/5', dot: 'bg-accent' },
  '支撑域': { border: 'border-blue-400/40', bg: 'bg-blue-400/5', dot: 'bg-blue-400' },
  '通用域': { border: 'border-amber-400/40', bg: 'bg-amber-400/5', dot: 'bg-amber-400' },
};

export function StatPill({ icon, label, count }: { icon: ReactNode; label: string; count: number }) {
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-border bg-bg-elevated px-2.5 py-1">
      {icon}
      <span className="text-[10px] text-text-muted">{label}</span>
      <span className="text-[11px] font-semibold text-text-primary">{count}</span>
    </div>
  );
}

/** BaaS provision 状态卡 (v6.19 续9 可观测性) — 让用户看到领域模型落地到 Supabase 的程度。
 *  provisioned: 显示 schema/表数/model版本; 未装配: 显示 reason (不再无错误可见)。 */
export function BaasProvisionCard({ baasStatus }: { baasStatus?: BaasStatus | null }) {
  if (!baasStatus) return null;

  if (!baasStatus.provisioned) {
    return (
      <div className="mb-4 flex items-start gap-2 rounded-lg border border-border bg-bg-elevated px-3 py-2">
        <Database size={12} className="mt-0.5 text-text-muted" />
        <div className="text-[11px]">
          <span className="font-medium text-text-secondary">BaaS 未装配</span>
          <p className="mt-0.5 text-text-muted">{baasStatus.reason || '领域模型提取后自动装配, 模型无聚合时跳过'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-4 flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2">
      <CheckCircle2 size={12} className="mt-0.5 text-emerald-500" />
      <div className="flex-1 text-[11px]">
        <span className="font-medium text-text-secondary">
          BaaS 已装配 · {baasStatus.status}
        </span>
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-text-muted">
          <span>schema: <code className="text-text-secondary">{baasStatus.schema_name}</code></span>
          {baasStatus.tables_count != null && <span>业务表 {baasStatus.tables_count}</span>}
          {baasStatus.last_applied_model_version != null && <span>model v{baasStatus.last_applied_model_version}</span>}
        </div>
      </div>
    </div>
  );
}

export function SubdomainCard({ subdomain, contexts }: { subdomain: DomainModelSubdomain; contexts: { name: string; description: string }[] }) {
  const style = SUBDOMAIN_STYLES[subdomain.type] || SUBDOMAIN_STYLES['通用域'];
  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} p-3`}>
      <div className="flex items-center gap-2">
        <Circle size={8} className={`fill-current ${style.dot.replace('bg-', 'text-')}`} />
        <span className="text-xs font-semibold text-text-primary">{subdomain.name}</span>
        <span className="rounded-full bg-bg-elevated px-1.5 py-0.5 text-[9px] text-text-tertiary">{subdomain.type}</span>
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

export function AggregateCard({ aggregate }: { aggregate: DomainModelAggregate }) {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Database size={12} className="text-accent" />
          <span className="text-xs font-semibold text-text-primary">{aggregate.name}</span>
        </div>
        {aggregate.context && (
          <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[9px] text-text-tertiary">{aggregate.context}</span>
        )}
      </div>
      {aggregate.description && (
        <p className="mt-1 text-[10px] text-text-secondary">{aggregate.description}</p>
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
      <span className="mt-0.5 w-8 flex-shrink-0 text-[9px] text-text-tertiary">{label}</span>
      <div className="flex flex-wrap gap-1">
        {items.map((item, i) => (
          <span key={i} className={`rounded px-1.5 py-0.5 text-[10px] ${color}`}>{item}</span>
        ))}
      </div>
    </div>
  );
}

export function ReviewButton({ review }: { review: ReturnType<typeof useDomainModelReview> }) {
  if (review.validating) {
    return (
      <button disabled className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-text-muted">
        <Loader2 size={10} className="animate-spin" /> 评审中...
      </button>
    );
  }

  if (review.reviewState === 'none') {
    return (
      <button
        onClick={review.validate}
        className="flex items-center gap-1 rounded-md border border-accent/40 bg-accent/5 px-2 py-1 text-[10px] font-medium text-accent transition-colors hover:bg-accent/10"
      >
        <ShieldCheck size={10} /> AI 评审
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={review.openValidation}
        className="flex items-center gap-1 rounded-md border border-emerald-500/40 bg-emerald-500/5 px-2 py-1 text-[10px] font-medium text-emerald-500 transition-colors hover:bg-emerald-500/10"
      >
        <CheckCircle2 size={10} /> 查看评审
      </button>
      {review.reviewState === 'stale' && (
        <span className="flex items-center gap-1 text-[10px] text-amber-500">
          <AlertTriangle size={10} />
          模型已变更
          <button
            onClick={review.validate}
            className="ml-0.5 underline hover:text-amber-400"
          >
            重新评审
          </button>
        </span>
      )}
    </div>
  );
}

export function isModelEmpty(dm: DomainModel): boolean {
  return (
    (!dm.subdomains || dm.subdomains.length === 0) &&
    (!dm.contexts || dm.contexts.length === 0) &&
    (!dm.aggregates || dm.aggregates.length === 0) &&
    (!dm.relations || dm.relations.length === 0)
  );
}
