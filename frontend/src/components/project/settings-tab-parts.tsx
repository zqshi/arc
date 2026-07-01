import type { ReactNode } from 'react';
import { FolderOpen, Lightbulb } from 'lucide-react';
import { Field } from './FormFields';

/** 本地工作目录选择 + 临时工作区迁移提示 */
export function LocalPathField({
  localPath,
  isTemporaryWorkspace,
  migrating,
  onPick,
}: {
  localPath: string;
  isTemporaryWorkspace: boolean;
  migrating: boolean;
  onPick: () => void;
}): ReactNode {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-medium text-text-tertiary">本地工作目录</label>
      <button
        type="button"
        onClick={onPick}
        className="flex h-9 w-full items-center gap-2 rounded-md border border-border bg-bg-input px-3 text-left text-sm transition-colors hover:border-border-active"
      >
        <FolderOpen size={14} className="flex-shrink-0 text-text-muted" />
        {localPath ? (
          <span className="flex-1 truncate font-mono text-xs text-text-primary">{localPath}</span>
        ) : (
          <span className="flex-1 truncate text-text-muted">点击选择目录...</span>
        )}
      </button>
      <p className="mt-1 text-[10px] text-text-muted">Coding Agent 将在此目录下读写代码</p>
      {isTemporaryWorkspace && (
        <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
          <p className="text-[11px] font-medium text-amber-400">⚡ 临时工作区</p>
          <p className="mt-0.5 text-[10px] text-text-muted">
            当前使用自动创建的临时目录。建议关联正式项目目录以便版本管理。
          </p>
          <button
            type="button"
            disabled={migrating}
            onClick={onPick}
            className="mt-1.5 rounded bg-amber-500/20 px-2 py-1 text-[10px] font-medium text-amber-300 hover:bg-amber-500/30 disabled:opacity-50"
          >
            {migrating ? '迁移中...' : '选择目录并迁移'}
          </button>
        </div>
      )}
    </div>
  );
}

/** 规范建议面板 (经验复用提示) */
export function InsightsPanel({
  insights,
  onAppendConvention,
}: {
  insights: Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }>;
  onAppendConvention: (solution: string) => void;
}): ReactNode {
  if (insights.length === 0) return null;
  return (
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
  );
}

/** 项目规范编辑块 (全宽) */
export function ConventionsField({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}): ReactNode {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
      <p className="mb-3 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">项目规范</p>
      <Field label="规范内容" value={value} onChange={onChange} multiline placeholder="AI在生成方案和代码时会遵守这些规范" />
    </div>
  );
}
