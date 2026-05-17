import { useState, useEffect, useCallback } from 'react';
import { Search } from 'lucide-react';
import { api } from '../api/client';
import type { Experience } from '../types/api';
import ExperienceDetailModal from '../components/ExperienceDetailModal';

export default function ExperienceList() {
  const [search, setSearch] = useState('');
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Experience | null>(null);

  const fetchExperiences = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listExperiences();
      setExperiences(data);
    } catch {
      setExperiences([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchExperiences();
  }, [fetchExperiences]);

  const filtered = experiences.filter(
    (e) =>
      !search ||
      e.title.toLowerCase().includes(search.toLowerCase()) ||
      e.problem.toLowerCase().includes(search.toLowerCase()) ||
      e.solution.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <h1 className="font-heading text-lg font-semibold text-text-primary">
            经验库
          </h1>
          <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-[11px] font-medium text-accent">
            {experiences.length}
          </span>
        </div>
        <div className="relative">
          <Search
            size={15}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            type="text"
            placeholder="搜索经验..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 w-56 rounded-md border border-border bg-bg-input pl-8 pr-3 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
          />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading ? (
          <div className="flex h-40 items-center justify-center text-xs text-text-muted">
            加载中...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-xs text-text-muted">
            {search ? '没有匹配的经验' : '暂无经验，完成待办后将自动提取'}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {filtered.map((exp) => (
              <div
                key={exp.id}
                onClick={() => setSelected(exp)}
                className="group cursor-pointer rounded-lg border border-border-active bg-bg-card p-4 transition-colors hover:border-accent/30 hover:bg-bg-elevated"
              >
                <h3 className="mb-1.5 text-sm font-medium text-text-primary">
                  {exp.title}
                </h3>
                <p className="mb-2 line-clamp-2 text-xs leading-relaxed text-text-secondary">
                  {exp.problem}
                </p>
                <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-text-secondary">
                  {exp.solution}
                </p>

                {exp.pitfalls.length > 0 && (
                  <div className="mb-3">
                    <span className="text-[10px] font-medium text-status-error/80">
                      踩坑: {exp.pitfalls[0]}
                    </span>
                  </div>
                )}

                <div className="mb-3 flex flex-wrap gap-1.5">
                  {exp.scope && exp.scope !== 'todo' && (
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      exp.scope === 'global'
                        ? 'bg-amber-500/15 text-amber-400'
                        : 'bg-sky-500/15 text-sky-400'
                    }`}>
                      {exp.scope === 'global' ? '全局' : '项目'}
                    </span>
                  )}
                  {exp.tags.map((tag) => (
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
                  <span>置信度 {Math.round(exp.confidence * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <ExperienceDetailModal experience={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
