import { useEffect, useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import type { DomainTemplate } from '../../api/client/templates';
import TemplateCard from './TemplateCard';

interface Props {
  /** 传入则显示"套用到项目"按钮 (ARCHITECTURE 阶段推荐场景) */
  projectId?: string;
  /** 初始展示模式: 'user' (用户模板) | 'search' (语义搜索) */
  mode?: 'user' | 'search';
}

/**
 * v5.7.0: 模板列表 + 语义搜索。
 *
 * 用户模板页: 列出当前用户的模板 (含 draft/published)。
 * ARCHITECTURE 推荐: 按需求语义搜索已发布模板。
 */
export default function TemplateList({ projectId, mode = 'user' }: Props) {
  const [templates, setTemplates] = useState<DomainTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [activeMode, setActiveMode] = useState(mode);

  const loadUser = async () => {
    setLoading(true);
    try {
      const data = await api.templates.listTemplates(0, 50);
      setTemplates(Array.isArray(data) ? data : (data as { items: DomainTemplate[] }).items);
    } finally {
      setLoading(false);
    }
  };

  const doSearch = async () => {
    if (!query.trim()) {
      loadUser();
      return;
    }
    setLoading(true);
    setActiveMode('search');
    try {
      const results = await api.templates.searchTemplates(query, 10);
      setTemplates(results);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUser();
  }, []);

  return (
    <div className="flex h-full flex-col gap-3">
      {/* 搜索栏 */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doSearch()}
            placeholder="语义搜索模板 (如: 电商订单系统)"
            className="w-full rounded-md border border-border bg-bg-card py-1.5 pl-9 pr-3 text-xs outline-none focus:border-accent"
          />
        </div>
        <button
          onClick={doSearch}
          disabled={loading}
          className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-xs text-white hover:bg-accent/90"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
          搜索
        </button>
        {activeMode === 'search' && (
          <button
            onClick={() => { setQuery(''); loadUser(); setActiveMode('user'); }}
            className="rounded-md px-3 py-1.5 text-xs text-text-secondary hover:bg-bg-elevated"
          >
            我的模板
          </button>
        )}
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto">
        {loading && templates.length === 0 ? (
          <div className="flex justify-center py-8">
            <Loader2 size={20} className="animate-spin text-accent" />
          </div>
        ) : templates.length === 0 ? (
          <div className="py-8 text-center text-xs text-text-muted">
            {activeMode === 'search' ? '无匹配模板' : '暂无模板, 完成项目发布后会自动提取'}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                template={t}
                projectId={projectId}
                onAction={activeMode === 'user' ? loadUser : doSearch}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
