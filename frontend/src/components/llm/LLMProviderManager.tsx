import { useState, useEffect, useCallback } from 'react';
import { Plus, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import type { LLMProvider, ProviderTemplate, VerifyResult } from '../../types/api';
import { ProviderCard, ProviderEditForm, type Draft } from './llm-provider-manager-parts';

interface LLMProviderManagerProps {
  onDefaultChanged?: () => void;
}

const EMPTY_DRAFT: Draft = {
  name: '', templateKey: 'openai', kind: 'openai_compatible',
  base_url: '', api_key: '', is_default: false, models: [],
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

  const patchEditing = (patch: Partial<Draft>) => {
    if (!editing) return;
    setEditing({ ...editing, ...patch });
    if ('base_url' in patch || 'api_key' in patch) {
      setVerifyResult(null);
    }
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
        <ProviderCard
          key={p.id}
          provider={p}
          onSetDefault={handleSetDefault}
          onEdit={startEdit}
          onDelete={handleDelete}
        />
      ))}

      {/* 添加/编辑表单 */}
      {editing && (
        <ProviderEditForm
          editing={editing}
          templates={templates}
          showKey={showKey}
          verifying={verifying}
          verifyResult={verifyResult}
          saving={saving}
          error={error}
          onToggleShowKey={() => setShowKey(!showKey)}
          onSelectTemplate={selectTemplate}
          onChangeField={patchEditing}
          onVerify={handleVerify}
          onCancel={() => { setEditing(null); setVerifyResult(null); }}
          onSave={handleSave}
        />
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
