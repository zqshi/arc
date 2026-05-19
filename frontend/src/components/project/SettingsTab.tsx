import { Save, Lightbulb, Settings } from 'lucide-react';
import { Field } from './FormFields';

interface SettingsTabProps {
  form: { name: string; description: string; tech_stack: string; repo_url: string; conventions: string };
  setForm: (f: SettingsTabProps['form']) => void;
  dirty: boolean;
  onSave: () => void;
  insights: Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }>;
  onAppendConvention: (solution: string) => void;
}

export function SettingsTab({ form, setForm, dirty, onSave, insights, onAppendConvention }: SettingsTabProps) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <Settings size={13} /> 项目设置
        </h2>
        <button
          onClick={onSave}
          disabled={!dirty}
          className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-[11px] font-medium text-white transition-opacity hover:bg-accent-hover disabled:opacity-30"
        >
          <Save size={12} /> 保存更改
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-bg-card p-4 space-y-4">
          <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide">基本信息</p>
          <Field label="项目名称" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
          <Field label="描述" value={form.description} onChange={(v) => setForm({ ...form, description: v })} multiline />
        </div>

        <div className="rounded-lg border border-border bg-bg-card p-4 space-y-4">
          <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide">技术配置</p>
          <Field label="技术栈" value={form.tech_stack} onChange={(v) => setForm({ ...form, tech_stack: v })} placeholder="例如：React + FastAPI + PostgreSQL" />
          <Field label="代码仓库" value={form.repo_url} onChange={(v) => setForm({ ...form, repo_url: v })} placeholder="https://github.com/..." />
        </div>

        <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
          <p className="mb-3 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">项目规范</p>
          <Field label="规范内容" value={form.conventions} onChange={(v) => setForm({ ...form, conventions: v })} multiline placeholder="AI在生成方案和代码时会遵守这些规范" />
        </div>

        {insights.length > 0 && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 lg:col-span-2">
            <p className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-amber-600">
              <Lightbulb size={13} /> 规范建议
            </p>
            <p className="mb-3 text-[11px] text-text-muted">以下经验已多次验证有效，建议纳入项目规范</p>
            <div className="space-y-2">
              {insights.map((ins) => (
                <div key={ins.id} className="flex items-start gap-3 rounded-md border border-amber-500/15 bg-bg-card p-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-text-primary">{ins.title}</p>
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-text-secondary">{ins.solution}</p>
                    <div className="mt-1 flex gap-2 text-[10px] text-text-muted">
                      <span>信心 {Math.round(ins.confidence * 100)}%</span>
                      <span>复用 {ins.reuse_count} 次</span>
                    </div>
                  </div>
                  <button
                    onClick={() => onAppendConvention(ins.solution)}
                    className="flex-shrink-0 rounded-md border border-amber-500/30 px-2 py-1 text-[10px] font-medium text-amber-600 hover:bg-amber-500/10"
                  >
                    纳入规范
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
