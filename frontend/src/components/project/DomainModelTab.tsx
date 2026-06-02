import { useState } from 'react';
import { Boxes, Layers, Network, Database, Zap, Circle, RefreshCw, Loader2, GitFork, ShieldCheck, AlertTriangle, CheckCircle2 } from 'lucide-react';
import type { DomainModel, DomainModelAggregate, DomainModelSubdomain } from '../../types/api';
import { DomainModelGraph } from './DomainModelGraph';
import ModelHistoryPanel from './ModelHistoryPanel';
import ValidationPanel from './ValidationPanel';
import type { useDomainModelReview } from '../../hooks/useDomainModelReview';

type ViewMode = 'strategic' | 'tactical' | 'all';

const SUBDOMAIN_STYLES: Record<string, { border: string; bg: string; dot: string }> = {
  '核心域': { border: 'border-accent/40', bg: 'bg-accent/5', dot: 'bg-accent' },
  '支撑域': { border: 'border-blue-400/40', bg: 'bg-blue-400/5', dot: 'bg-blue-400' },
  '通用域': { border: 'border-amber-400/40', bg: 'bg-amber-400/5', dot: 'bg-amber-400' },
};

interface DomainModelTabProps {
  projectId?: string;
  domainModel: DomainModel | null;
  loading: boolean;
  review: ReturnType<typeof useDomainModelReview>;
  onRefresh?: () => Promise<void>;
  refreshing?: boolean;
  onExtractFromCode?: () => Promise<void>;
  extractingFromCode?: boolean;
  hasLocalPath?: boolean;
}

export function DomainModelTab({ projectId, domainModel, loading, review, onRefresh, refreshing, onExtractFromCode, extractingFromCode, hasLocalPath }: DomainModelTabProps) {
  const [view, setView] = useState<ViewMode>('all');
  const [graphMode, setGraphMode] = useState(false);

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
        {hasLocalPath ? (
          <>
            <p className="mt-1 max-w-sm text-xs text-text-muted">
              已关联代码仓库。可以直接从源码中提取领域模型（实体、值对象、聚合、限界上下文等）。
            </p>
            {onExtractFromCode && (
              <button
                onClick={onExtractFromCode}
                disabled={extractingFromCode}
                className="mt-4 flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {extractingFromCode ? (
                  <><Loader2 size={13} className="animate-spin" /> 正在从代码中提取...</>
                ) : (
                  <><Database size={13} /> 从代码库提取领域模型</>
                )}
              </button>
            )}
            <p className="mt-3 max-w-sm text-[10px] text-text-muted">
              也可以在对话中产出「技术架构」交付物后自动提取。两种来源会自动合并。
            </p>
          </>
        ) : (
          <p className="mt-1 max-w-sm text-xs text-text-muted">
            配置本地工作目录后可从代码直接提取，或在对话中产出「技术架构」交付物后自动提取。
            随着需求迭代，领域模型会持续累积完善。
          </p>
        )}
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
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary disabled:opacity-50"
            >
              {refreshing ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
              刷新模型
            </button>
          )}
          <ReviewButton review={review} />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setGraphMode(!graphMode)}
            className={`flex h-7 w-7 items-center justify-center rounded-md border transition-colors ${
              graphMode ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-text-muted hover:bg-bg-elevated hover:text-text-secondary'
            }`}
            title={graphMode ? '切换为卡片视图' : '切换为依赖关系图'}
          >
            <GitFork size={13} />
          </button>
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
      </div>

      {/* Stats */}
      <div className="mb-4 flex gap-3">
        <StatPill icon={<Layers size={11} />} label="子域" count={(domainModel.subdomains || []).length} />
        <StatPill icon={<Network size={11} />} label="上下文" count={(domainModel.contexts || []).length} />
        <StatPill icon={<Database size={11} />} label="聚合" count={(domainModel.aggregates || []).length} />
        <StatPill icon={<Zap size={11} />} label="关系" count={(domainModel.relations || []).length + (domainModel.aggregate_relations?.length || 0)} />
      </div>

      {graphMode ? (
        <DomainModelGraph domainModel={domainModel} view={view} />
      ) : (
        <>
          {/* Strategic View */}
          {(view === 'strategic' || view === 'all') && (domainModel.subdomains || []).length > 0 && (
            <section className="mb-5">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">子域划分</h4>
              <div className="grid gap-2">
                {(domainModel.subdomains || []).map((sd) => (
                  <SubdomainCard key={sd.name} subdomain={sd} contexts={(domainModel.contexts || []).filter(c => c.subdomain === sd.name)} />
                ))}
              </div>
            </section>
          )}

          {/* Context Relations */}
          {(view === 'strategic' || view === 'all') && (domainModel.relations || []).length > 0 && (
            <section className="mb-5">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">上下文关系</h4>
              <div className="space-y-1.5">
                {(domainModel.relations || []).map((rel, i) => (
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
          {(view === 'tactical' || view === 'all') && (domainModel.aggregates || []).length > 0 && (
            <section className="mb-5">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">聚合模型</h4>
              <div className="grid gap-2 sm:grid-cols-2">
                {(domainModel.aggregates || []).map((agg) => (
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
        </>
      )}

      {/* Updated timestamp */}
      {domainModel.updated_at && (
        <p className="mt-4 text-[10px] text-text-muted">
          最后更新: {new Date(domainModel.updated_at).toLocaleString('zh-CN')}
        </p>
      )}

      {/* Validation Result Panel (includes feedback actions) */}
      {review.showValidation && review.lastValidation && (
        <ValidationPanel
          validation={review.lastValidation}
          onClose={review.closeValidation}
          reviewState={review.reviewState}
          lastReviewedVersion={review.lastReviewedVersion}
          currentVersion={domainModel?.version || 0}
          onRevalidate={review.validate}
          revalidating={review.validating}
          feedbacks={review.feedbacks}
          onResolveFeedback={review.resolveFeedback}
        />
      )}

      {/* Model Version History */}
      {projectId && (
        <div className="mt-4">
          <ModelHistoryPanel
            snapshots={review.snapshots}
            currentVersion={domainModel?.version || 0}
            loading={review.snapshotsLoading}
            onRollback={review.rollbackModel}
          />
        </div>
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

function ReviewButton({ review }: { review: ReturnType<typeof useDomainModelReview> }) {
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

function isModelEmpty(dm: DomainModel): boolean {
  return (
    (!dm.subdomains || dm.subdomains.length === 0) &&
    (!dm.contexts || dm.contexts.length === 0) &&
    (!dm.aggregates || dm.aggregates.length === 0) &&
    (!dm.relations || dm.relations.length === 0)
  );
}
