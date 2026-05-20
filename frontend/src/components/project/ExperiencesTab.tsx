import { Lightbulb, Check, Archive, ArrowUpRight } from 'lucide-react';
import type { Experience, ExperienceStatus, ExperienceCategory } from '../../types/api';
import { EXPERIENCE_STATUS_LABELS, EXPERIENCE_CATEGORY_LABELS } from '../../types/api';
import { ExperienceListSkeleton } from '../Skeleton';

const expStatusStyle: Record<ExperienceStatus, { bg: string; dot: string }> = {
  draft: { bg: 'bg-amber-500/15 text-amber-600', dot: 'bg-amber-500' },
  confirmed: { bg: 'bg-status-done/15 text-status-done', dot: 'bg-status-done' },
  archived: { bg: 'bg-text-muted/15 text-text-muted', dot: 'bg-text-muted' },
};

const categoryColor: Record<ExperienceCategory, string> = {
  technical: 'bg-blue-500/15 text-blue-500',
  business_rule: 'bg-emerald-500/15 text-emerald-500',
  pitfall: 'bg-red-500/15 text-red-500',
  architecture_decision: 'bg-purple-500/15 text-purple-500',
  scope_change: 'bg-amber-500/15 text-amber-500',
  estimation: 'bg-cyan-500/15 text-cyan-500',
};

interface ExperiencesTabProps {
  experiences: Experience[];
  loading: boolean;
  filter: 'all' | 'draft' | 'confirmed';
  setFilter: (f: 'all' | 'draft' | 'confirmed') => void;
  categoryFilter: ExperienceCategory | 'all';
  setCategoryFilter: (c: ExperienceCategory | 'all') => void;
  onConfirm: (id: string) => void;
  onArchive: (id: string) => void;
  onPromote: (id: string) => void;
}

export function ExperiencesTab({ experiences, loading, filter, setFilter, categoryFilter, setCategoryFilter, onConfirm, onArchive, onPromote }: ExperiencesTabProps) {
  const filters: { key: typeof filter; label: string }[] = [
    { key: 'all', label: '全部' },
    { key: 'draft', label: '待审核' },
    { key: 'confirmed', label: '已确认' },
  ];

  const categoryFilters: { key: ExperienceCategory | 'all'; label: string }[] = [
    { key: 'all', label: '全部类型' },
    { key: 'technical', label: '技术' },
    { key: 'business_rule', label: '业务规则' },
    { key: 'pitfall', label: '踩坑' },
    { key: 'architecture_decision', label: '架构决策' },
    { key: 'scope_change', label: '范围变更' },
    { key: 'estimation', label: '估算校准' },
  ];

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <Lightbulb size={13} /> 项目经验
        </h2>
        <div className="flex gap-1">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                filter === f.key ? 'bg-accent/10 text-accent' : 'text-text-tertiary hover:text-text-secondary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Category filter */}
      <div className="mb-3 flex flex-wrap gap-1">
        {categoryFilters.map((c) => (
          <button
            key={c.key}
            onClick={() => setCategoryFilter(c.key)}
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors ${
              categoryFilter === c.key ? 'bg-accent/15 text-accent' : 'bg-bg-elevated text-text-muted hover:text-text-secondary'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {loading ? (
        <ExperienceListSkeleton />
      ) : experiences.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg-card p-6 text-center">
          <Lightbulb size={28} className="mx-auto mb-2 text-text-muted" strokeWidth={1.2} />
          <p className="text-xs text-text-secondary">暂无经验</p>
          <p className="mt-1 text-[11px] text-text-muted">完成需求后，AI会自动提取经验</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {experiences.map((exp) => {
            const style = expStatusStyle[exp.status];
            return (
              <div key={exp.id} className="rounded-lg border border-border bg-bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${style.dot}`} />
                      <h3 className="truncate text-sm font-medium text-text-primary">{exp.title}</h3>
                      <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${style.bg}`}>
                        {EXPERIENCE_STATUS_LABELS[exp.status]}
                      </span>
                      {exp.category && exp.category !== 'technical' && (
                        <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${categoryColor[exp.category] || ''}`}>
                          {EXPERIENCE_CATEGORY_LABELS[exp.category] || exp.category}
                        </span>
                      )}
                      {exp.scope === 'personal' && (
                        <span className="rounded-full bg-purple-500/15 px-1.5 py-0.5 text-[9px] font-medium text-purple-500">个人</span>
                      )}
                    </div>
                    {exp.problem && <p className="mt-1.5 line-clamp-2 text-xs text-text-secondary">{exp.problem}</p>}
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-text-muted">
                      <span>信心 {Math.round(exp.confidence * 100)}%</span>
                      <span>复用 {exp.reuse_count} 次</span>
                      {exp.tags.length > 0 && (
                        <div className="flex gap-1">
                          {exp.tags.slice(0, 3).map((t) => (
                            <span key={t.label} className="rounded px-1 py-0.5" style={{ backgroundColor: `${t.color}18`, color: t.color }}>{t.label}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-1">
                    {exp.status === 'draft' && (
                      <button onClick={() => onConfirm(exp.id)} className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-status-done hover:text-status-done" title="确认经验">
                        <Check size={10} /> 确认
                      </button>
                    )}
                    {exp.status !== 'archived' && (
                      <button onClick={() => onArchive(exp.id)} className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-text-muted hover:text-text-muted" title="归档">
                        <Archive size={10} />
                      </button>
                    )}
                    {exp.scope === 'project' && exp.status === 'confirmed' && (
                      <button onClick={() => onPromote(exp.id)} className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-purple-500 hover:text-purple-500" title="升级为个人经验">
                        <ArrowUpRight size={10} /> 个人
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
