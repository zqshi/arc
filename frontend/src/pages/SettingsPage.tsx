import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Server, Bot, Cpu, CheckCircle, XCircle } from 'lucide-react';
import { api } from '../api/client';
import { LLMConfigSection } from '../components/project/LLMConfigSection';
import type { SystemSettings } from '../types/api';

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState<Record<string, string>>({});

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const [s, h] = await Promise.all([
          api.getSettings(),
          fetch(`${import.meta.env.VITE_API_URL || ''}/health`).then(r => r.json()),
        ]);
        setSettings(s);
        setHealthStatus(h);
      } catch {
        setSettings(null);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  if (loading) {
    return <div className="flex h-full items-center justify-center text-sm text-text-muted">加载中...</div>;
  }

  if (!settings) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-status-error">
        无法连接后端服务
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex items-center gap-2 border-b border-border px-6 py-4">
        <SettingsIcon size={18} className="text-text-secondary" />
        <h1 className="font-heading text-lg font-semibold text-text-primary">系统设置</h1>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {/* Health status */}
          <section className="rounded-lg border border-border bg-bg-card p-4">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
              <Server size={13} /> 服务状态
            </h2>
            <div className="flex items-center gap-4">
              <StatusBadge
                label="后端"
                ok={healthStatus.status === 'ok' || healthStatus.status === 'degraded'}
              />
              <StatusBadge label="数据库" ok={healthStatus.database === 'connected'} />
              <StatusBadge
                label="LLM"
                ok={
                  (settings.llm_provider === 'openai' && settings.openai_api_key_set) ||
                  (settings.llm_provider === 'anthropic' && settings.anthropic_api_key_set) ||
                  (settings.llm_provider === 'deepseek' && settings.deepseek_api_key_set)
                }
              />
            </div>
          </section>

          {/* Usage & Plan — hidden for now (single-user mode) */}

          {/* LLM Configuration — Editable */}
          <section className="rounded-lg border border-border bg-bg-card p-4">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
              <Cpu size={13} /> LLM 配置
            </h2>
            <LLMConfigSection
              config={{
                provider: settings.llm_provider,
                model: (settings as unknown as Record<string, unknown>)[`${settings.llm_provider}_model`] as string || '',
                base_url: (settings as unknown as Record<string, unknown>)[`${settings.llm_provider}_base_url`] as string || '',
              }}
              onChange={async (config) => {
                try {
                  const payload: Record<string, string> = {};
                  if (config.provider) payload.llm_provider = config.provider;
                  if (config.model) payload[`${config.provider || settings.llm_provider}_model`] = config.model;
                  if (config.base_url) payload[`${config.provider || settings.llm_provider}_base_url`] = config.base_url;
                  if (config.api_key) payload[`${config.provider || settings.llm_provider}_api_key`] = config.api_key;
                  await api.updateSettings(payload);
                  // 刷新展示
                  const s = await api.getSettings();
                  setSettings(s);
                } catch { /* */ }
              }}
              showSaveHint
            />
          </section>

          {/* Agent Config */}
          <section className="rounded-lg border border-border bg-bg-card p-4">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
              <Bot size={13} /> Coding Agent 配置
            </h2>
            <div className="space-y-2">
              <InfoRow label="默认 Agent" value={settings.agent_default || '未配置'} />
              <InfoRow
                label="OpenHands"
                value={settings.openhands_url || '未配置'}
                ok={settings.openhands_api_key_set || !!settings.openhands_url}
              />
              <InfoRow
                label="开发阶段覆盖"
                value={settings.agent_development || '(使用默认)'}
              />
              <InfoRow
                label="测试阶段覆盖"
                value={settings.agent_testing || '(使用默认)'}
              />
              <InfoRow
                label="部署阶段覆盖"
                value={settings.agent_deployment || '(使用默认)'}
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ label, ok, small }: { label: string; ok: boolean; small?: boolean }) {
  return (
    <span
      className={`flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ${
        small ? 'text-[9px]' : 'text-[11px]'
      } ${ok ? 'bg-status-done/15 text-status-done' : 'bg-status-error/15 text-status-error'}`}
    >
      {ok ? <CheckCircle size={small ? 9 : 11} /> : <XCircle size={small ? 9 : 11} />}
      {label}
    </span>
  );
}

function InfoRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-border/50 px-3 py-2">
      <span className="text-[11px] text-text-secondary">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-text-primary">{value}</span>
        {ok !== undefined && (
          <span className={ok ? 'text-status-done' : 'text-status-error'}>
            {ok ? <CheckCircle size={11} /> : <XCircle size={11} />}
          </span>
        )}
      </div>
    </div>
  );
}
