import {
  Bot, Check, X, Loader2, Trash2, Star, RefreshCw, Eye, EyeOff, ChevronDown,
} from 'lucide-react';
import type { LLMProvider, ProviderTemplate, VerifyResult } from '../../types/api';

export const ERROR_LABEL: Record<string, string> = {
  invalid_key: 'API Key 无效或鉴权失败',
  http_error: '服务端返回错误',
  network: '无法连接 (网络/超时/端点不可达)',
  unknown: '未知错误',
  '': '',
};

export type Draft = {
  id?: string;
  name: string;
  templateKey: string;
  kind: 'openai_compatible' | 'anthropic';
  base_url: string;
  api_key: string;
  is_default: boolean;
  models: string[];
};

/** 厂商列表项卡片 */
export function ProviderCard({
  provider,
  onSetDefault,
  onEdit,
  onDelete,
}: {
  provider: LLMProvider;
  onSetDefault: (id: string) => void;
  onEdit: (p: LLMProvider) => void;
  onDelete: (id: string) => void;
}) {
  const p = provider;
  return (
    <div className="rounded-md border border-border bg-bg-elevated/30 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot size={14} className="text-accent" />
          <span className="text-sm font-medium text-text-primary">{p.name}</span>
          {p.is_default && (
            <span className="flex items-center gap-1 rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">
              <Star size={10} /> 默认
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {!p.is_default && (
            <button onClick={() => onSetDefault(p.id)} title="设为默认" className="rounded p-1 text-text-muted hover:text-accent">
              <Star size={13} />
            </button>
          )}
          <button onClick={() => onEdit(p)} title="编辑" className="rounded p-1 text-text-muted hover:text-text-secondary">
            <ChevronDown size={13} className="rotate-0" />
          </button>
          <button onClick={() => onDelete(p.id)} title="删除" className="rounded p-1 text-text-muted hover:text-status-error">
            <Trash2 size={13} />
          </button>
        </div>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-text-tertiary">
        <span>{p.kind}</span>
        <span className="truncate">{p.base_url || '(默认端点)'}</span>
        <span>{p.api_key_set ? '✓ Key 已配' : '✗ 未配 Key'}</span>
        <span>{p.models.length} 个模型</span>
      </div>
    </div>
  );
}

/** 添加/编辑凭证表单 */
export function ProviderEditForm({
  editing,
  templates,
  showKey,
  verifying,
  verifyResult,
  saving,
  error,
  onToggleShowKey,
  onSelectTemplate,
  onChangeField,
  onVerify,
  onCancel,
  onSave,
}: {
  editing: Draft;
  templates: ProviderTemplate[];
  showKey: boolean;
  verifying: boolean;
  verifyResult: VerifyResult | null;
  saving: boolean;
  error: string;
  onToggleShowKey: () => void;
  onSelectTemplate: (key: string) => void;
  onChangeField: (patch: Partial<Draft>) => void;
  onVerify: () => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  return (
    <div className="space-y-3 rounded-md border border-border-active/40 bg-bg-input/20 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary">{editing.id ? '编辑凭证' : '添加凭证'}</span>
        <button onClick={onCancel} className="text-text-muted hover:text-text-secondary">
          <X size={14} />
        </button>
      </div>

      {/* 模板选择 (仅新建) */}
      {!editing.id && (
        <div>
          <label className="mb-1 block text-[10px] font-medium text-text-tertiary">厂商模板</label>
          <div className="flex flex-wrap gap-1.5">
            {templates.map((t) => (
              <button
                key={t.key}
                onClick={() => onSelectTemplate(t.key)}
                className={`rounded border px-2 py-1 text-[11px] transition-colors ${
                  editing.templateKey === t.key
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border text-text-secondary hover:border-border-active'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <label className="mb-1 block text-[10px] font-medium text-text-tertiary">名称</label>
        <input
          value={editing.name}
          onChange={(e) => onChangeField({ name: e.target.value })}
          placeholder="如 我的OpenAI / 国内代理"
          className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary focus:border-border-active focus:outline-none"
        />
      </div>

      <div>
        <label className="mb-1 block text-[10px] font-medium text-text-tertiary">Base URL</label>
        <input
          value={editing.base_url}
          onChange={(e) => { onChangeField({ base_url: e.target.value }); }}
          placeholder="https://api.openai.com/v1"
          className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary focus:border-border-active focus:outline-none"
        />
      </div>

      <div>
        <label className="mb-1 block text-[10px] font-medium text-text-tertiary">
          API Key {editing.id && '(留空不修改)'}
        </label>
        <div className="relative">
          <input
            type={showKey ? 'text' : 'password'}
            value={editing.api_key}
            onChange={(e) => { onChangeField({ api_key: e.target.value }); }}
            placeholder="sk-..."
            className="h-8 w-full rounded-md border border-border bg-bg-input px-3 pr-9 text-xs text-text-primary focus:border-border-active focus:outline-none"
          />
          <button
            onClick={onToggleShowKey}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
          >
            {showKey ? <EyeOff size={13} /> : <Eye size={13} />}
          </button>
        </div>
      </div>

      {/* 验证按钮 + 结果 */}
      <div className="flex items-center gap-2">
        <button
          onClick={onVerify}
          disabled={verifying || !editing.api_key}
          className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-[11px] text-text-secondary hover:border-border-active disabled:opacity-40"
        >
          {verifying ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          验证并拉取模型
        </button>
        {verifyResult?.valid && (
          <span className="flex items-center gap-1 text-[11px] text-status-success">
            <Check size={12} /> 有效 · {verifyResult.models.length} 个模型
          </span>
        )}
        {verifyResult && !verifyResult.valid && (
          <span className="flex items-center gap-1 text-[11px] text-status-error">
            <X size={12} /> {ERROR_LABEL[verifyResult.error_kind] || verifyResult.error_kind}
          </span>
        )}
      </div>

      {/* 模型清单 */}
      {editing.models.length > 0 && (
        <div>
          <label className="mb-1 block text-[10px] font-medium text-text-tertiary">
            模型清单 ({editing.kind === 'anthropic' ? '静态建议 (该协议无在线拉取)' : '验证后拉取'})
          </label>
          <div className="flex flex-wrap gap-1">
            {editing.models.map((m) => (
              <span key={m} className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] text-text-secondary">{m}</span>
            ))}
          </div>
        </div>
      )}

      <label className="flex items-center gap-2 text-[11px] text-text-secondary">
        <input
          type="checkbox"
          checked={editing.is_default}
          onChange={(e) => onChangeField({ is_default: e.target.checked })}
          className="accent-accent"
        />
        设为默认 LLM
      </label>

      {error && <p className="text-[11px] text-status-error">{error}</p>}

      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="rounded-md px-3 py-1.5 text-[11px] text-text-muted hover:text-text-secondary"
        >
          取消
        </button>
        <button
          onClick={onSave}
          disabled={saving}
          className="rounded-md bg-accent px-3 py-1.5 text-[11px] text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {saving ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  );
}
