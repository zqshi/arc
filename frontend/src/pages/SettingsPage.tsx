import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Server, Bot, Cpu, CheckCircle, XCircle, CreditCard } from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { SystemSettings, UsageResponse } from '../types/api';

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState<Record<string, string>>({});
  const [usage, setUsage] = useState<UsageResponse | null>(null);

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
        try {
          setUsage(await api.getUsage());
        } catch (e) {
          if (!(e instanceof ApiError && e.status === 400)) throw e;
        }
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

  const providerLabels: Record<string, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    deepseek: 'DeepSeek',
  };

  const providerConfigs = [
    {
      key: 'openai',
      label: 'OpenAI',
      model: settings.openai_model,
      baseUrl: settings.openai_base_url,
      keySet: settings.openai_api_key_set,
    },
    {
      key: 'anthropic',
      label: 'Anthropic',
      model: settings.anthropic_model,
      baseUrl: settings.anthropic_base_url,
      keySet: settings.anthropic_api_key_set,
    },
    {
      key: 'deepseek',
      label: 'DeepSeek',
      model: settings.deepseek_model,
      baseUrl: settings.deepseek_base_url,
      keySet: settings.deepseek_api_key_set,
    },
  ];

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

          {/* Usage & Plan */}
          {usage && (
            <section className="rounded-lg border border-border bg-bg-card p-4">
              <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                <CreditCard size={13} /> 用量与套餐
              </h2>
              <div className="mb-3 rounded-md bg-accent/10 px-3 py-2">
                <span className="text-xs text-text-secondary">
                  当前套餐:{' '}
                  <span className="font-semibold text-accent uppercase">{usage.plan}</span>
                </span>
              </div>
              <div className="space-y-2">
                <UsageBar label="项目" used={usage.projects_used} limit={usage.projects_limit} />
                <UsageBar label="成员" used={usage.members_used} limit={usage.members_limit} />
                <UsageBar label="今日 AI 调用" used={usage.ai_calls_today} limit={usage.ai_calls_limit} />
              </div>
            </section>
          )}

          {/* LLM Provider */}
          <section className="rounded-lg border border-border bg-bg-card p-4">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
              <Cpu size={13} /> LLM 配置
            </h2>
            <div className="mb-3 rounded-md bg-accent/10 px-3 py-2">
              <span className="text-xs text-text-secondary">
                当前使用:{' '}
                <span className="font-semibold text-accent">
                  {providerLabels[settings.llm_provider] || settings.llm_provider}
                </span>
              </span>
            </div>
            <div className="space-y-3">
              {providerConfigs.map((p) => (
                <div
                  key={p.key}
                  className={`rounded-md border p-3 ${
                    settings.llm_provider === p.key
                      ? 'border-accent/40 bg-accent/5'
                      : 'border-border'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-text-primary">{p.label}</span>
                      {settings.llm_provider === p.key && (
                        <span className="rounded-full bg-accent/15 px-1.5 py-0.5 text-[9px] font-medium text-accent">
                          活跃
                        </span>
                      )}
                    </div>
                    <StatusBadge label="API Key" ok={p.keySet} small />
                  </div>
                  <div className="mt-2 space-y-1 text-[11px] text-text-muted">
                    <p>模型: <span className="text-text-secondary">{p.model}</span></p>
                    <p>端点: <span className="text-text-secondary">{p.baseUrl || '(默认)'}</span></p>
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[10px] text-text-muted">
              修改配置请编辑项目根目录 <code className="rounded bg-bg-elevated px-1 py-0.5">.env</code> 文件后重启后端服务
            </p>
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

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const nearLimit = pct >= 80;
  const atLimit = pct >= 100;
  return (
    <div className="rounded-md border border-border/50 px-3 py-2">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[11px] text-text-secondary">{label}</span>
        <span className={`text-[11px] font-medium ${atLimit ? 'text-status-error' : nearLimit ? 'text-amber-500' : 'text-text-primary'}`}>
          {used} / {limit}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/30">
        <div
          className={`h-full rounded-full transition-all ${atLimit ? 'bg-status-error' : nearLimit ? 'bg-amber-400' : 'bg-accent'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
