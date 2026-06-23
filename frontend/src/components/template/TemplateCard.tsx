import { useState } from 'react';
import { Check, X, Loader2, FileText, TrendingUp } from 'lucide-react';
import { api } from '../../api/client';
import type { DomainTemplate } from '../../api/client/templates';

const CATEGORY_LABELS: Record<string, string> = {
  crud_app: 'CRUD 应用',
  workflow: '工作流',
  ecommerce: '电商',
  social: '社交',
  saas_backend: 'SaaS 后台',
  custom: '自定义',
};

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  confirmed: '已确认',
  published: '已发布',
  deprecated: '已废弃',
};

interface Props {
  template: DomainTemplate;
  /** 可选: 用于 apply 的目标 project_id */
  projectId?: string;
  onAction?: () => void;
}

/**
 * v5.7.0: 单个模板卡片 + 生命周期操作 + apply 确认。
 */
export default function TemplateCard({ template, projectId, onAction }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [applying, setApplying] = useState(false);
  const [requirement, setRequirement] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async (action: 'confirm' | 'publish' | 'deprecate') => {
    setError(null);
    try {
      if (action === 'confirm') await api.templates.confirmTemplate(template.id);
      if (action === 'publish') await api.templates.publishTemplate(template.id);
      if (action === 'deprecate') await api.templates.deprecateTemplate(template.id);
      onAction?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败');
    }
  };

  const handleApply = async () => {
    if (!projectId) return;
    setApplying(true);
    setError(null);
    try {
      await api.templates.applyTemplate({
        template_id: template.id,
        project_id: projectId,
        requirement: requirement || template.title,
        model_version: 1,
      });
      setConfirming(false);
      onAction?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '套用失败');
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileText size={14} className="text-accent" />
          <h3 className="text-sm font-medium text-text-primary">{template.title}</h3>
        </div>
        <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted">
          {STATUS_LABELS[template.status] || template.status}
        </span>
      </div>

      <p className="mb-2 text-[11px] text-text-secondary">{template.description}</p>

      <div className="mb-2 flex flex-wrap gap-1.5">
        <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">
          {CATEGORY_LABELS[template.category] || template.category}
        </span>
        {template.entity_patterns.slice(0, 2).map((p, i) => (
          <span key={i} className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted">
            {p}
          </span>
        ))}
      </div>

      <div className="mb-3 flex items-center gap-3 text-[10px] text-text-muted">
        <span className="flex items-center gap-1">
          <TrendingUp size={10} /> 使用 {template.usage_count} 次
        </span>
        <span>成功率 {Math.round(template.success_rate * 100)}%</span>
        <span>置信 {Math.round(template.confidence * 100)}%</span>
      </div>

      {error && (
        <div className="mb-2 rounded bg-status-error/10 px-2 py-1 text-[10px] text-status-error">
          {error}
        </div>
      )}

      {confirming && projectId ? (
        <div className="mb-2 space-y-2 rounded-md border border-border bg-bg-elevated p-2">
          <p className="text-[11px] text-text-secondary">
            套用此模板到当前项目? 将适配并 provision Supabase schema。
          </p>
          <textarea
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            placeholder="描述你的需求 (留空用模板标题)"
            className="w-full rounded border border-border bg-bg-card p-2 text-[11px] outline-none"
            rows={2}
          />
          <div className="flex justify-end gap-1.5">
            <button
              onClick={() => setConfirming(false)}
              disabled={applying}
              className="flex items-center gap-1 rounded px-2 py-1 text-[10px] text-text-secondary hover:bg-bg-card"
            >
              <X size={11} /> 取消
            </button>
            <button
              onClick={handleApply}
              disabled={applying}
              className="flex items-center gap-1 rounded bg-accent px-2 py-1 text-[10px] text-white hover:bg-accent/90"
            >
              {applying ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
              确认套用
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {template.status === 'draft' && (
            <button
              onClick={() => handleConfirm('confirm')}
              className="rounded bg-status-success/10 px-2 py-1 text-[10px] text-status-success hover:bg-status-success/20"
            >
              确认可用
            </button>
          )}
          {template.status === 'confirmed' && (
            <button
              onClick={() => handleConfirm('publish')}
              className="rounded bg-accent/10 px-2 py-1 text-[10px] text-accent hover:bg-accent/20"
            >
              发布
            </button>
          )}
          {template.status === 'published' && projectId && (
            <button
              onClick={() => setConfirming(true)}
              className="rounded bg-accent px-2 py-1 text-[10px] text-white hover:bg-accent/90"
            >
              套用到项目
            </button>
          )}
          {template.status !== 'deprecated' && template.status !== 'draft' && (
            <button
              onClick={() => handleConfirm('deprecate')}
              className="rounded px-2 py-1 text-[10px] text-text-muted hover:bg-bg-elevated"
            >
              废弃
            </button>
          )}
        </div>
      )}
    </div>
  );
}
