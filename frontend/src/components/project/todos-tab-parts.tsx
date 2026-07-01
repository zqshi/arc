import type { VersionStatus, VersionType } from '../../types/api';

export const VERSION_STATUS_STYLE: Record<VersionStatus, { bg: string; label: string }> = {
  planning: { bg: 'bg-status-pending/15 text-status-pending', label: '规划中' },
  active: { bg: 'bg-accent/15 text-accent', label: '进行中' },
  released: { bg: 'bg-status-done/15 text-status-done', label: '已发布' },
};

export interface VersionForm {
  show: boolean;
  setShow: (v: boolean) => void;
  name: string;
  setName: (v: string) => void;
  goal: string;
  setGoal: (v: string) => void;
  type: VersionType;
  setType: (v: VersionType) => void;
  create: () => void;
}

export interface VersionActions {
  activate: (id: string) => void;
  release: (id: string) => void;
  remove: (id: string, name: string) => void;
  analyze?: (id: string) => void;
  setCreateForVersion: (id: string) => void;
}

export interface TodoActions {
  delete: (todoId: string, todoTitle: string, versionId: string) => void;
  resume?: (todoId: string) => void;
  complete?: (todoId: string) => void;
  reopen?: (todoId: string) => void;
}

/** 版本创建表单 */
export function VersionCreateForm({ form }: { form: VersionForm }) {
  return (
    <div className="mb-3 rounded-lg border border-accent/30 bg-bg-card p-4">
      <div className="mb-3">
        <input
          type="text"
          value={form.goal}
          onChange={(e) => form.setGoal(e.target.value)}
          placeholder="版本目标（一句话描述本迭代要做什么）"
          className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
          autoFocus
        />
      </div>
      <div className="mb-3 flex gap-2">
        {([
          { key: 'major', label: '大版本', desc: 'x.0' },
          { key: 'minor', label: '功能迭代', desc: '_.x' },
          { key: 'patch', label: '修复补丁', desc: '_._.x' },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => form.setType(t.key)}
            className={`flex-1 rounded-md border px-2 py-1.5 text-center text-[11px] font-medium transition-colors ${
              form.type === t.key
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-border text-text-tertiary hover:text-text-secondary'
            }`}
          >
            {t.label} <span className="text-text-muted">({t.desc})</span>
          </button>
        ))}
      </div>
      <div className="mb-3">
        <input
          type="text"
          value={form.name}
          onChange={(e) => form.setName(e.target.value)}
          placeholder="版本号（留空按类型自动生成）"
          className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
        />
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={() => form.setShow(false)} className="rounded-md border border-border px-3 py-1 text-xs text-text-secondary">取消</button>
        <button onClick={form.create} className="rounded-md bg-accent px-3 py-1 text-xs text-white hover:bg-accent-hover">创建</button>
      </div>
    </div>
  );
}
