import { useState, useEffect, useCallback, useRef } from 'react';
import { Search, Lightbulb, FolderOpen } from 'lucide-react';
import { api } from '../api/client';
import { ExperienceListSkeleton } from '../components/Skeleton';
import type { Experience, ExperienceStatus, Project } from '../types/api';
import { EXPERIENCE_STATUS_LABELS } from '../types/api';
import ExperienceDetailModal from '../components/ExperienceDetailModal';

type FilterTab = 'all' | 'personal' | 'project';

export default function ExperienceList() {
  const [search, setSearch] = useState('');
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [searchResults, setSearchResults] = useState<Experience[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<Experience | null>(null);
  const [tab, setTab] = useState<FilterTab>('all');
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  const fetchExperiences = useCallback(async () => {
    setLoading(true);
    try {
      const scope = tab === 'all' ? undefined : tab;
      const data = await api.listExperiences({
        scope,
        project_id: selectedProjectId || undefined,
      });
      setExperiences(data);
    } catch {
      setExperiences([]);
    } finally {
      setLoading(false);
    }
  }, [tab, selectedProjectId]);

  useEffect(() => {
    fetchExperiences();
  }, [fetchExperiences]);

  useEffect(() => {
    clearTimeout(searchTimer.current);
    if (!search.trim()) {
      setSearchResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const results = await api.searchExperiences(search.trim(), selectedProjectId || undefined);
        setSearchResults(results);
      } catch {
        setSearchResults(null);
      } finally {
        setSearching(false);
      }
    }, 400);
    return () => clearTimeout(searchTimer.current);
  }, [search, selectedProjectId]);

  const displayList = searchResults ?? experiences;

  const tabs: { key: FilterTab; label: string }[] = [
    { key: 'all', label: '全部' },
    { key: 'personal', label: '个人经验' },
    { key: 'project', label: '项目经验' },
  ];

  const expStatusStyle: Record<ExperienceStatus, { bg: string; dot: string }> = {
    draft: { bg: 'bg-amber-500/15 text-amber-600', dot: 'bg-amber-500' },
    confirmed: { bg: 'bg-status-done/15 text-status-done', dot: 'bg-status-done' },
    archived: { bg: 'bg-text-muted/15 text-text-muted', dot: 'bg-text-muted' },
  };

  const handleModalAction = () => {
    setSelected(null);
    fetchExperiences();
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <h1 className="font-heading text-lg font-semibold text-text-primary">
            经验库
          </h1>
          <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-[11px] font-medium text-accent">
            {experiences.length}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <nav className="flex gap-1">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  tab === t.key
                    ? 'bg-accent/10 text-accent'
                    : 'text-text-tertiary hover:text-text-secondary'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>

          {tab === 'project' && projects.length > 0 && (
            <div className="relative">
              <FolderOpen
                size={13}
                className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-text-muted"
              />
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="h-8 w-40 appearance-none rounded-md border border-border bg-bg-input pl-7 pr-6 text-[11px] text-text-primary focus:border-border-active focus:outline-none"
              >
                <option value="">全部项目</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="relative">
            <Search
              size={15}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              placeholder="语义搜索经验..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-56 rounded-md border border-border bg-bg-input pl-8 pr-3 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
            />
            {searching && (
              <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
                <div className="h-3 w-3 animate-spin rounded-full border border-accent border-t-transparent" />
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading || searching ? (
          <ExperienceListSkeleton />
        ) : displayList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
            <Lightbulb size={36} className="mb-3 text-text-muted" strokeWidth={1.2} />
            <p className="text-xs text-text-secondary">
              {search ? '没有匹配的经验，试试更换关键词' : '暂无经验，完成需求后将自动提取'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 animate-fade-in lg:grid-cols-2">
            {displayList.map((exp) => {
              const style = expStatusStyle[exp.status];
              return (
                <div
                  key={exp.id}
                  onClick={() => setSelected(exp)}
                  className="group cursor-pointer rounded-lg border border-border bg-bg-card p-4 transition-colors hover:border-accent/30 hover:bg-bg-elevated"
                >
                  <div className="mb-1.5 flex items-center gap-2">
                    <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${style.dot}`} />
                    <h3 className="truncate text-sm font-medium text-text-primary">
                      {exp.title}
                    </h3>
                    <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${style.bg}`}>
                      {EXPERIENCE_STATUS_LABELS[exp.status]}
                    </span>
                  </div>

                  <p className="mb-2 line-clamp-2 text-xs leading-relaxed text-text-secondary">
                    {exp.problem}
                  </p>

                  {exp.pitfalls.length > 0 && (
                    <div className="mb-2">
                      <span className="text-[10px] font-medium text-status-error/80">
                        踩坑: {exp.pitfalls[0]}
                      </span>
                    </div>
                  )}

                  <div className="mb-2 flex flex-wrap gap-1.5">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      exp.scope === 'personal'
                        ? 'bg-purple-500/15 text-purple-500'
                        : 'bg-sky-500/15 text-sky-400'
                    }`}>
                      {exp.scope === 'personal' ? '个人' : '项目'}
                    </span>
                    {exp.tags.slice(0, 3).map((tag) => (
                      <span
                        key={tag.label}
                        className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                        style={{
                          backgroundColor: `${tag.color}18`,
                          color: tag.color,
                        }}
                      >
                        {tag.label}
                      </span>
                    ))}
                  </div>

                  <div className="flex items-center gap-3 text-[10px] text-text-muted">
                    <span>复用 {exp.reuse_count} 次</span>
                    <span className="h-0.5 w-0.5 rounded-full bg-text-muted" />
                    <span>信心 {Math.round(exp.confidence * 100)}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <ExperienceDetailModal
        experience={selected}
        onClose={() => setSelected(null)}
        onAction={handleModalAction}
      />
    </div>
  );
}
