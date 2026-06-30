import { useState, useEffect, useCallback } from 'react';
import {
  Bot, Plus, Check, X, Loader2, Trash2, Star, RefreshCw, Eye, EyeOff, ChevronDown,
} from 'lucide-react';
import { api } from '../../api/client';
import type { LLMProvider, ProviderTemplate, VerifyResult } from '../../types/api';

interface LLMProviderManagerProps {
  onDefaultChanged?: () => void;
}

type Draft = {
  id?: string; // 编辑时填
  name: string;
  templateKey: string;
  kind: 'openai_compatible' | 'anthropic';
  base_url: string;
  api_key: string; // 留空=不改 (编辑时)
  is_default: boolean;
  models: string[];
};

const EMPTY_DRAFT: Draft = {
  name: '', templateKey: 'openai', kind: 'openai_compatible',
  base_url: '', api_key: '', is_default: false, models: [],
};

const ERROR_LABEL: Record<string, string> = {
  invalid_key: 'API Key 无效或鉴权失败',
  http_error: '服务端返回错误',
  network: '无法连接 (网络/超时/端点不可达)',
  unknown: '未知错误',
  '': '',
};

export function LLMProviderManager({ onDefaultChanged }: LLMProviderManagerProps) {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [templates, setTemplates] = useState<ProviderTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Draft | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ps, ts] = await Promise.all([api.listProviders(), api.listProviderTemplates()]);
      setProviders(ps);
      setTemplates(ts);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const selectTemplate = (key: string) => {
    const t = templates.find((x) => x.key === key);
    if (!t || !editing) return;
    setEditing({
      ...editing,
      templateKey: key,
      kind: t.kind,
      base_url: t.default_base_url,
      name: editing.name || t.label,
      models: [...t.suggested_models],
    });
    setVerifyResult(null);
  };

  const handleVerify = async () => {
    if (!editing || !editing.api_key) {
      setVerifyResult({ valid: false, models: [], error_kind: 'invalid_key', error_message: '请先填写 API Key' });
      return;
    }
    setVerifying(true);
    setVerifyResult(null);
    try {
      const result = await api.verifyCredentials({
        kind: editing.kind,
        base_url: editing.base_url,
        api_key: editing.api_key,
      });
      setVerifyResult(result);
      if (result.valid && result.models.length > 0) {
        setEditing({ ...editing, models: result.models });
      }
    } catch (e) {
      setVerifyResult({
        valid: false, models: [], error_kind: 'unknown',
        error_message: e instanceof Error ? e.message : '验证请求失败',
      });
    } finally {
      setVerifying(false);
    }
  };

  const handleSave = async () => {
    if (!editing) return;
    if (!editing.name.trim()) { setError('请填写名称'); return; }
    setSaving(true);
    setError('');
    try {
      if (editing.id) {
        await api.updateProvider(editing.id, {
          name: editing.name,
          base_url: editing.base_url,
          api_key: editing.api_key || undefined,
          is_default: editing.is_default || undefined,
        });
      } else {
        if (!editing.api_key) { setError('新建凭证需填写 API Key'); setSaving(false); return; }
        await api.createProvider({
          name: editing.name,
          kind: editing.kind,
          base_url: editing.base_url,
          api_key: editing.api_key,
          is_default: editing.is_default,
        });
      }
      setEditing(null);
      setVerifyResult(null);
      await load();
      onDefaultChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('删除该厂商凭证?')) return;
    try {
      await api.deleteProvider(id);
      await load();
      onDefaultChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await api.updateProvider(id, { is_default: true });
      await load();
      onDefaultChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '设置失败');
    }
  };

  const startEdit = (p?: LLMProvider) => {
    setVerifyResult(null);
    setError('');
    setShowKey(false);
    if (p) {
      setEditing({
        id: p.id, name: p.name, templateKey: '', kind: p.kind,
        base_url: p.base_url, api_key: '', is_default: p.is_default, models: p.models,
      });
    } else {
      const t = templates.find((x) => x.key === 'openai');
      setEditing({
        ...EMPTY_DRAFT,
        base_url: t?.default_base_url || '',
        name: t?.label || '',
        models: t ? [...t.suggested_models] : [],
      });
    }
  };

  if (loading) {
    return <div className="flex items-center gap-2 text-sm text-text-muted"><Loader2 size={14} className="animate-spin" /> 加载中...</div>;
  }

  return (
    <div className="space-y-3">
      {/* 厂商列表 */}
      {providers.length === 0 && !editing && (
        <p className="text-xs text-text-muted">尚未配置任何 LLM 厂商,点击下方添加。</p>
      )}
      {providers.map((p) => (
        <div key={p.id} className="rounded-md border border-border bg-bg-elevated/30 p-3">
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
                <button onClick={() => handleSetDefault(p.id)} title="设为默认" className="rounded p-1 text-text-muted hover:text-accent">
                  <Star size={13} />
                </button>
              )}
              <button onClick={() => startEdit(p)} title="编辑" className="rounded p-1 text-text-muted hover:text-text-secondary">
                <ChevronDown size={13} className="rotate-0" />
              </button>
              <button onClick={() => handleDelete(p.id)} title="删除" className="rounded p-1 text-text-muted hover:text-status-error">
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
      ))}

      {/* 添加/编辑表单 */}
      {editing && (
        <div className="space-y-3 rounded-md border border-border-active/40 bg-bg-input/20 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-secondary">{editing.id ? '编辑凭证' : '添加凭证'}</span>
            <button onClick={() => { setEditing(null); setVerifyResult(null); }} className="text-text-muted hover:text-text-secondary">
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
                    onClick={() => selectTemplate(t.key)}
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
              onChange={(e) => setEditing({ ...editing, name: e.target.value })}
              placeholder="如 我的OpenAI / 国内代理"
              className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary focus:border-border-active focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-medium text-text-tertiary">Base URL</label>
            <input
              value={editing.base_url}
              onChange={(e) => { setEditing({ ...editing, base_url: e.target.value }); setVerifyResult(null); }}
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
                onChange={(e) => { setEditing({ ...editing, api_key: e.target.value }); setVerifyResult(null); }}
                placeholder="sk-..."
                className="h-8 w-full rounded-md border border-border bg-bg-input px-3 pr-9 text-xs text-text-primary focus:border-border-active focus:outline-none"
              />
              <button
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
              >
                {showKey ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>
          </div>

          {/* 验证按钮 + 结果 */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleVerify}
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
              onChange={(e) => setEditing({ ...editing, is_default: e.target.checked })}
              className="accent-accent"
            />
            设为默认 LLM
          </label>

          {error && <p className="text-[11px] text-status-error">{error}</p>}

          <div className="flex justify-end gap-2">
            <button
              onClick={() => { setEditing(null); setVerifyResult(null); }}
              className="rounded-md px-3 py-1.5 text-[11px] text-text-muted hover:text-text-secondary"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-accent px-3 py-1.5 text-[11px] text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      )}

      {/* 添加按钮 */}
      {!editing && (
        <button
          onClick={() => startEdit()}
          className="flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-border py-2 text-[11px] text-text-muted hover:border-border-active hover:text-text-secondary"
        >
          <Plus size={13} /> 添加 LLM 厂商
        </button>
      )}

      {error && !editing && <p className="text-[11px] text-status-error">{error}</p>}
    </div>
  );
}
