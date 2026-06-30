import { useState } from 'react';
import { Layers, Network, Database, Zap, RefreshCw, Loader2, GitFork } from 'lucide-react';
import type { DomainModel, BaasStatus } from '../../types/api';
import { DomainModelGraph } from './DomainModelGraph';
import ModelHistoryPanel from './ModelHistoryPanel';
import ValidationPanel from './ValidationPanel';
import type { useDomainModelReview } from '../../hooks/useDomainModelReview';
import { StatPill, BaasProvisionCard, SubdomainCard, AggregateCard, ReviewButton, isModelEmpty } from './domain-model-tab-parts';

type ViewMode = 'strategic' | 'tactical' | 'all';

interface DomainModelTabProps {
  projectId?: string;
  domainModel: DomainModel | null;
  loading: boolean;
  review: ReturnType<typeof useDomainModelReview>;
  baasStatus?: BaasStatus | null;
  onRefresh?: () => Promise<void>;
  refreshing?: boolean;
  onExtractFromCode?: () => Promise<void>;
  extractingFromCode?: boolean;
  hasLocalPath?: boolean;
}

export function DomainModelTab({ projectId, domainModel, loading, review, baasStatus, onRefresh, refreshing, onExtractFromCode, extractingFromCode, hasLocalPath }: DomainModelTabProps) {
  const [view, setView] = useState<ViewMode>(() => {
    return (localStorage.getItem('arc:domainModel:view') as ViewMode) || 'all';
  });
  const [graphMode, setGraphMode] = useState(() => {
    return localStorage.getItem('arc:domainModel:graphMode') === 'true';
  });

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
        <Database size={32} className="mb-3 text-text-muted/30" />
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
      {/* Header — 与 TodosTab/SettingsTab 布局一致 */}
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <Database size={13} /> 领域模型
          {domainModel.version != null && (
            <span className="rounded-full bg-bg-elevated px-2 py-0.5 text-[10px] font-normal normal-case tracking-normal text-text-muted">
              v{domainModel.version}
            </span>
          )}
        </h2>
        <div className="flex items-center gap-2">
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
      </div>

      {/* View switcher */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex gap-3">
          <button
            onClick={() => { const next = !graphMode; setGraphMode(next); localStorage.setItem('arc:domainModel:graphMode', String(next)); }}
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
                onClick={() => { setView(key); localStorage.setItem('arc:domainModel:view', key); }}
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

      {/* BaaS provision 状态 (v6.19 续9 可观测性) — 领域模型落地到 Supabase 的程度 */}
      <BaasProvisionCard baasStatus={baasStatus} />

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
                    {rel.description && <span className="ml-auto text-text-secondary">{rel.description}</span>}
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
