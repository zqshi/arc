import { CodeBlock, LabeledField, SectionTitle } from './shared';
import { asString } from './utils';

interface Endpoint {
  method?: string;
  path?: string;
  description?: string;
  auth_required?: boolean;
}

interface Content {
  data_model_ref?: string;
  data_persistence?: string;
  endpoints?: Endpoint[];
  auth_strategy?: string;
  external_api_base?: string | null;
  notes?: string;
}

const PERSISTENCE_LABELS: Record<string, string> = {
  none: '无 (纯前端)',
  embedded: '前端嵌入式 (localStorage/IndexedDB)',
  external: '对接已有后端',
  supabase: 'Supabase BaaS (v5.6.0 启用)',
};

/**
 * v5.5.0: SERVICE_SPEC artifact 渲染器。
 * v5.6.0 BaaS 接入锚点 — 当前 data_persistence="supabase" 为声明态不可执行。
 */
export default function ServiceSpec({ content }: { content: Content }) {
  const persistence = content.data_persistence ?? 'none';
  const persistenceLabel = PERSISTENCE_LABELS[persistence] ?? persistence;
  const isSupabaseDeclared = persistence === 'supabase';

  return (
    <div className="space-y-4">
      <SectionTitle>服务契约</SectionTitle>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <LabeledField label="领域模型引用" value={content.data_model_ref} mono />
        <LabeledField label="认证策略" value={content.auth_strategy} />
        <LabeledField label="数据持久化" value={persistenceLabel} />
        {content.external_api_base && (
          <LabeledField label="外部 API" value={content.external_api_base} mono />
        )}
      </div>

      {isSupabaseDeclared && (
        <div className="rounded-md border border-status-warning/30 bg-status-warning/5 px-3 py-2 text-[11px] text-status-warning">
          ⚠ 已声明 Supabase BaaS，但运行时接入在 v5.6.0 上线后才可用。当前仅为契约声明。
        </div>
      )}

      {content.endpoints && content.endpoints.length > 0 && (
        <div>
          <SectionTitle>API 端点 ({content.endpoints.length})</SectionTitle>
          <div className="space-y-1.5">
            {content.endpoints.map((ep, i) => (
              <div
                key={`${ep.method}-${ep.path}-${i}`}
                className="flex items-center gap-2 rounded border border-border bg-bg-elevated px-2.5 py-1.5 text-[11px]"
              >
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                    ep.method === 'GET'
                      ? 'bg-status-info/15 text-status-info'
                      : ep.method === 'POST'
                        ? 'bg-status-success/15 text-status-success'
                        : ep.method === 'DELETE'
                          ? 'bg-status-error/15 text-status-error'
                          : 'bg-accent/15 text-accent'
                  }`}
                >
                  {ep.method ?? '?'}
                </span>
                <span className="font-mono text-text-primary">{ep.path ?? '?'}</span>
                {ep.description && (
                  <span className="flex-1 text-text-muted">— {ep.description}</span>
                )}
                {ep.auth_required === false && (
                  <span className="text-[10px] text-text-muted">无需认证</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {content.notes && (
        <div>
          <SectionTitle>备注</SectionTitle>
          <p className="text-xs text-text-secondary">{content.notes}</p>
        </div>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-[11px] text-text-muted">原始 JSON</summary>
        <CodeBlock>{asString(content)}</CodeBlock>
      </details>
    </div>
  );
}

