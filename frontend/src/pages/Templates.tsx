import { useState, useEffect, useCallback } from 'react';
import { LayoutTemplate, Search, CheckCircle2, Upload, Archive, Rocket } from 'lucide-react';
import { api } from '../api/client';
import type { Template, TemplateStatus } from '../types/api';

const STATUS_LABELS: Record<TemplateStatus, string> = {
  draft: '草稿', confirmed: '已确认', published: '已发布', deprecated: '已废弃',
};
const STATUS_COLORS: Record<TemplateStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  confirmed: 'bg-blue-100 text-blue-700',
  published: 'bg-green-100 text-green-700',
  deprecated: 'bg-red-100 text-red-700',
};

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [searching, setSearching] = useState(false);
  const [applyTarget, setApplyTarget] = useState<Template | null>(null);
  const [applyForm, setApplyForm] = useState({ projectId: '', requirement: '', supabaseUrl: '' });

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setTemplates(await api.listTemplates());
    } catch {
      setError('加载模板失败');
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleSearch = async () => {
    if (!search.trim()) { fetchTemplates(); return; }
    setSearching(true);
    setError('');
    try {
      setTemplates(await api.searchTemplates(search.trim()));
    } catch {
      setError('搜索失败');
    } finally {
      setSearching(false);
    }
  };

  const handleStatusAction = async (template: Template, action: 'confirm' | 'publish' | 'deprecate') => {
    try {
      const fn = { confirm: api.confirmTemplate, publish: api.publishTemplate, deprecate: api.deprecateTemplate }[action];
      const updated = await fn(template.id);
      setTemplates((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch {
      setError(`${action} 失败, 检查状态前置 (draft→confirm→publish)`);
    }
  };

  const handleApply = async () => {
    if (!applyTarget || !applyForm.projectId.trim() || !applyForm.requirement.trim()) return;
    try {
      await api.applyTemplate(applyTarget.id, applyForm.projectId.trim(), applyForm.requirement.trim(), applyForm.supabaseUrl.trim());
      setApplyTarget(null);
      setApplyForm({ projectId: '', requirement: '', supabaseUrl: '' });
      setError('');
      alert('模板应用已提交');
    } catch {
      setError('应用失败, 仅 published 模板可应用');
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center gap-2">
        <LayoutTemplate className="h-6 w-6 text-primary" />
        <h1 className="text-xl font-semibold">模板市场</h1>
      </div>

      <div className="mb-4 flex gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="语义搜索已发布模板…"
          className="flex-1 rounded-md border border-border px-3 py-1.5 text-sm"
        />
        <button onClick={handleSearch} className="flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-sm text-white hover:opacity-90">
          <Search className="h-4 w-4" /> {searching ? '搜索中' : '搜索'}
        </button>
        {search && <button onClick={() => { setSearch(''); fetchTemplates(); }} className="rounded-md border border-border px-3 py-1.5 text-sm">清除</button>}
      </div>

      {error && <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="text-text-muted">加载中…</div>
      ) : templates.length === 0 ? (
        <div className="rounded-lg border border-border p-8 text-center text-text-muted">
          {search ? '未找到匹配模板' : '暂无模板, 模板由项目版本经验抽取生成'}
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <div key={t.id} className="rounded-lg border border-border bg-bg-card p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{t.title}</span>
                    <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLORS[t.status]}`}>{STATUS_LABELS[t.status]}</span>
                    <span className="rounded bg-bg-muted px-2 py-0.5 text-xs">{t.category}</span>
                  </div>
                  <p className="mt-1 text-sm text-text-muted line-clamp-2">{t.description || '(无描述)'}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-text-muted">
                    <span>用量 {t.usage_count}</span>
                    <span>成功率 {Math.round(t.success_rate * 100)}%</span>
                    <span>置信度 {Math.round(t.confidence * 100)}%</span>
                    {t.tags.map((tag) => <span key={tag} className="rounded bg-bg-muted px-1.5 py-0.5">#{tag}</span>)}
                  </div>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3">
                {t.status === 'draft' && (
                  <button onClick={() => handleStatusAction(t, 'confirm')} className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-bg-muted">
                    <CheckCircle2 className="h-3 w-3" /> 确认
                  </button>
                )}
                {t.status === 'confirmed' && (
                  <button onClick={() => handleStatusAction(t, 'publish')} className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-bg-muted">
                    <Upload className="h-3 w-3" /> 发布
                  </button>
                )}
                {t.status !== 'deprecated' && t.status !== 'draft' && (
                  <button onClick={() => handleStatusAction(t, 'deprecate')} className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-bg-muted">
                    <Archive className="h-3 w-3" /> 废弃
                  </button>
                )}
                {t.status === 'published' && (
                  <button onClick={() => { setApplyTarget(t); setApplyForm({ projectId: '', requirement: '', supabaseUrl: '' }); }} className="flex items-center gap-1 rounded bg-primary px-2 py-1 text-xs text-white hover:opacity-90">
                    <Rocket className="h-3 w-3" /> 应用到项目
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {applyTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setApplyTarget(null)}>
          <div className="w-96 rounded-lg bg-bg-card p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">应用模板: {applyTarget.title}</h2>
            <label className="mb-3 block">
              <span className="text-sm text-text-muted">目标项目 ID</span>
              <input value={applyForm.projectId} onChange={(e) => setApplyForm({ ...applyForm, projectId: e.target.value })} className="mt-1 w-full rounded border border-border px-2 py-1.5" placeholder="project uuid" />
            </label>
            <label className="mb-3 block">
              <span className="text-sm text-text-muted">需求描述</span>
              <textarea value={applyForm.requirement} onChange={(e) => setApplyForm({ ...applyForm, requirement: e.target.value })} className="mt-1 w-full rounded border border-border px-2 py-1.5" rows={3} placeholder="项目需求, 用于适配模板" />
            </label>
            <label className="mb-4 block">
              <span className="text-sm text-text-muted">Supabase URL (可选)</span>
              <input value={applyForm.supabaseUrl} onChange={(e) => setApplyForm({ ...applyForm, supabaseUrl: e.target.value })} className="mt-1 w-full rounded border border-border px-2 py-1.5" placeholder="https://...supabase.co" />
            </label>
            <div className="flex justify-end gap-2">
              <button onClick={() => setApplyTarget(null)} className="rounded border border-border px-3 py-1.5 text-sm">取消</button>
              <button onClick={handleApply} className="rounded bg-primary px-3 py-1.5 text-sm text-white">应用</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
