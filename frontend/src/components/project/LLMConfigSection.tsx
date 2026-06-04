import { useState } from 'react';
import { Bot, Eye, EyeOff, ChevronDown } from 'lucide-react';

interface LLMConfig {
  provider?: string;
  model?: string;
  api_key?: string;
  base_url?: string;
  temperature?: number;
  max_tokens?: number;
}

interface LLMConfigSectionProps {
  config: LLMConfig;
  onChange: (config: LLMConfig) => void;
  showSaveHint?: boolean;
}

const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'custom', label: '自定义' },
];

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'o1', 'o3-mini'],
  anthropic: ['claude-sonnet-4-6', 'claude-opus-4-8', 'claude-haiku-4-5-20251001'],
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  custom: [],
};

export function LLMConfigSection({ config, onChange, showSaveHint }: LLMConfigSectionProps) {
  const [showKey, setShowKey] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const provider = config.provider || 'openai';
  const models = MODEL_SUGGESTIONS[provider] || [];

  const update = (patch: Partial<LLMConfig>) => { onChange({ ...config, ...patch }); setDirty(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onChange({ ...config });
      setDirty(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Bot size={14} className="text-accent" />
        <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide">AI 模型配置</p>
      </div>

      {/* Provider */}
      <div>
        <label className="mb-1 block text-[11px] font-medium text-text-tertiary">Provider</label>
        <div className="relative">
          <select
            value={provider}
            onChange={(e) => update({ provider: e.target.value, model: '' })}
            className="h-9 w-full appearance-none rounded-md border border-border bg-bg-input px-3 pr-8 text-sm text-text-primary focus:border-border-active focus:outline-none"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
          <ChevronDown size={14} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
        </div>
      </div>

      {/* Model */}
      <div>
        <label className="mb-1 block text-[11px] font-medium text-text-tertiary">模型</label>
        <input
          type="text"
          list="model-suggestions"
          value={config.model || ''}
          onChange={(e) => update({ model: e.target.value })}
          placeholder={models[0] || '输入模型名称'}
          className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
        />
        {models.length > 0 && (
          <datalist id="model-suggestions">
            {models.map((m) => <option key={m} value={m} />)}
          </datalist>
        )}
      </div>

      {/* API Key */}
      <div>
        <label className="mb-1 block text-[11px] font-medium text-text-tertiary">API Key</label>
        <div className="relative">
          <input
            type={showKey ? 'text' : 'password'}
            value={config.api_key || ''}
            onChange={(e) => update({ api_key: e.target.value })}
            placeholder="sk-..."
            className="h-9 w-full rounded-md border border-border bg-bg-input px-3 pr-9 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
          >
            {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <p className="mt-1 text-[10px] text-text-muted">密钥仅存储在服务端，不会明文展示</p>
      </div>

      {/* Advanced toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center gap-1 text-[11px] text-text-muted hover:text-text-secondary"
      >
        <ChevronDown size={12} className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
        高级选项
      </button>

      {showAdvanced && (
        <div className="space-y-3 rounded-md border border-border/50 bg-bg-elevated/30 p-3">
          {/* Base URL */}
          <div>
            <label className="mb-1 block text-[10px] font-medium text-text-tertiary">自定义端点 (Base URL)</label>
            <input
              type="text"
              value={config.base_url || ''}
              onChange={(e) => update({ base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
              className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
            />
          </div>

          {/* Temperature */}
          <div>
            <label className="mb-1 flex items-center justify-between text-[10px] font-medium text-text-tertiary">
              <span>Temperature</span>
              <span className="tabular-nums text-text-muted">{config.temperature ?? 0.7}</span>
            </label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={config.temperature ?? 0.7}
              onChange={(e) => update({ temperature: parseFloat(e.target.value) })}
              className="w-full accent-accent"
            />
          </div>

          {/* Max tokens */}
          <div>
            <label className="mb-1 block text-[10px] font-medium text-text-tertiary">Max Tokens</label>
            <input
              type="number"
              value={config.max_tokens ?? 16384}
              onChange={(e) => update({ max_tokens: parseInt(e.target.value) || 16384 })}
              className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary focus:border-border-active focus:outline-none"
            />
          </div>
        </div>
      )}

      {showSaveHint && dirty && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="mt-3 w-full rounded-md bg-accent px-4 py-2 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
        >
          {saving ? '保存中...' : '保存配置'}
        </button>
      )}
    </div>
  );
}
