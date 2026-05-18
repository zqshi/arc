import { useState, useEffect } from 'react';
import { Save, X } from 'lucide-react';

interface FieldDef {
  key: string;
  label: string;
  multiline?: boolean;
  placeholder?: string;
}

const ARTIFACT_FIELDS: Record<string, FieldDef[]> = {
  requirement_spec: [
    { key: 'background', label: '需求背景', multiline: true, placeholder: '为什么要做这件事' },
    { key: 'user_scenarios', label: '用户场景', multiline: true, placeholder: '用户如何使用' },
    { key: 'goals', label: '目标', multiline: true, placeholder: '做完后达成什么效果' },
    { key: 'boundaries', label: '边界条件', multiline: true, placeholder: '不做什么、约束是什么' },
    { key: 'acceptance_criteria', label: '验收标准', multiline: true, placeholder: '怎么算做完了' },
    { key: 'risk_assessment', label: '风险评估', multiline: true, placeholder: '有哪些风险点' },
  ],
  tech_architecture: [
    { key: 'overview', label: '方案概述', multiline: true },
    { key: 'tech_stack', label: '技术选型', multiline: true },
    { key: 'system_design', label: '系统设计', multiline: true },
    { key: 'api_design', label: 'API 设计', multiline: true },
    { key: 'data_model', label: '数据模型', multiline: true },
    { key: 'deployment', label: '部署方案', multiline: true },
  ],
  ui_design: [
    { key: 'design_philosophy', label: '设计理念', multiline: true },
    { key: 'layout', label: '布局方案', multiline: true },
    { key: 'components', label: '组件描述', multiline: true },
    { key: 'interactions', label: '交互说明', multiline: true },
    { key: 'wireframe', label: '线框图描述', multiline: true },
  ],
  dev_report: [
    { key: 'summary', label: '开发总结', multiline: true },
    { key: 'changes', label: '变更内容', multiline: true },
    { key: 'issues', label: '遇到的问题', multiline: true },
    { key: 'next_steps', label: '后续计划', multiline: true },
  ],
  test_report: [
    { key: 'summary', label: '测试总结', multiline: true },
    { key: 'test_cases', label: '测试用例', multiline: true },
    { key: 'results', label: '测试结果', multiline: true },
    { key: 'issues', label: '发现的问题', multiline: true },
  ],
  deploy_report: [
    { key: 'summary', label: '部署总结', multiline: true },
    { key: 'steps', label: '部署步骤', multiline: true },
    { key: 'config_changes', label: '配置变更', multiline: true },
    { key: 'verification', label: '验证结果', multiline: true },
  ],
  experience_card: [
    { key: 'title', label: '标题', multiline: false },
    { key: 'problem', label: '问题描述', multiline: true },
    { key: 'solution', label: '解决方案', multiline: true },
    { key: 'applicable_scenarios', label: '适用场景', multiline: true },
  ],
};

interface Props {
  artifactType: string;
  content: Record<string, unknown>;
  onSave: (content: Record<string, unknown>) => void;
  onCancel: () => void;
}

export default function ArtifactEditor({ artifactType, content, onSave, onCancel }: Props) {
  const fields = ARTIFACT_FIELDS[artifactType];
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [jsonMode, setJsonMode] = useState(false);
  const [jsonDraft, setJsonDraft] = useState('');

  useEffect(() => {
    const initial: Record<string, string> = {};
    if (fields) {
      for (const f of fields) {
        const val = content[f.key];
        initial[f.key] = typeof val === 'string' ? val : val ? JSON.stringify(val, null, 2) : '';
      }
    }
    setDraft(initial);
    setJsonDraft(JSON.stringify(content, null, 2));
  }, [content, artifactType]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFieldChange = (key: string, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    if (jsonMode) {
      try {
        const parsed = JSON.parse(jsonDraft);
        onSave(parsed);
      } catch {
        return;
      }
    } else {
      const result: Record<string, unknown> = { ...content };
      for (const [k, v] of Object.entries(draft)) {
        result[k] = v;
      }
      onSave(result);
    }
  };

  if (!fields) {
    return (
      <div className="flex h-full flex-col gap-2">
        <textarea
          value={jsonDraft}
          onChange={(e) => setJsonDraft(e.target.value)}
          className="flex-1 resize-none rounded-lg border border-border bg-bg-input p-4 font-mono text-xs leading-relaxed text-text-secondary focus:border-accent focus:outline-none"
        />
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary">
            取消
          </button>
          <button onClick={handleSave} className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-xs text-white hover:bg-accent-hover">
            <Save size={11} /> 保存
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <button
          onClick={() => setJsonMode(!jsonMode)}
          className="text-[10px] text-text-muted hover:text-text-secondary"
        >
          {jsonMode ? '切换为表单模式' : '切换为 JSON 模式'}
        </button>
        <div className="flex items-center gap-2">
          <button onClick={onCancel} className="text-text-muted hover:text-text-primary">
            <X size={14} />
          </button>
          <button onClick={handleSave} className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-[11px] font-medium text-white hover:bg-accent-hover">
            <Save size={11} /> 保存
          </button>
        </div>
      </div>

      {jsonMode ? (
        <textarea
          value={jsonDraft}
          onChange={(e) => setJsonDraft(e.target.value)}
          className="flex-1 resize-none rounded-lg border border-border bg-bg-input p-4 font-mono text-xs leading-relaxed text-text-secondary focus:border-accent focus:outline-none"
        />
      ) : (
        <div className="flex-1 space-y-4 overflow-y-auto">
          {fields.map((f) => (
            <div key={f.key}>
              <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">
                {f.label}
              </label>
              {f.multiline ? (
                <textarea
                  value={draft[f.key] || ''}
                  onChange={(e) => handleFieldChange(f.key, e.target.value)}
                  rows={4}
                  placeholder={f.placeholder}
                  className="w-full resize-none rounded-md border border-border bg-bg-input px-3 py-2 text-xs leading-relaxed text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
                />
              ) : (
                <input
                  type="text"
                  value={draft[f.key] || ''}
                  onChange={(e) => handleFieldChange(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
