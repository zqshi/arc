import {
  Plus,
  GitBranch,
  Play,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Trash2,
} from 'lucide-react';
import type { Version, VersionStatus, VersionType, Todo, TodoStatus } from '../../types/api';
import { STATUS_LABELS } from '../../types/api';
import ActionMenu from '../ActionMenu';
import type { ActionMenuItem } from '../ActionMenu';
import PhaseProgress from '../PhaseProgress';

const VERSION_STATUS_STYLE: Record<VersionStatus, { bg: string; label: string }> = {
  planning: { bg: 'bg-status-pending/15 text-status-pending', label: '规划中' },
  active: { bg: 'bg-accent/15 text-accent', label: '进行中' },
  released: { bg: 'bg-status-done/15 text-status-done', label: '已发布' },
};

const statusDotColor: Record<TodoStatus, string> = {
  pending: 'bg-status-pending',
  active: 'bg-accent',
  done: 'bg-status-done',
  error: 'bg-status-error',
};

const statusBadgeBg: Record<TodoStatus, string> = {
  pending: 'bg-status-pending/15 text-status-pending',
  active: 'bg-accent/15 text-accent',
  done: 'bg-status-done/15 text-status-done',
  error: 'bg-status-error/15 text-status-error',
};

interface TodosTabProps {
  versions: Version[];
  versionTodos: Record<string, Todo[]>;
  expandedVersions: Set<string>;
  toggleVersion: (id: string) => void;
  showNewVersion: boolean;
  setShowNewVersion: (v: boolean) => void;
  versionName: string;
  setVersionName: (v: string) => void;
  versionGoal: string;
  setVersionGoal: (v: string) => void;
  versionType: VersionType;
  setVersionType: (v: VersionType) => void;
  handleCreateVersion: () => void;
  handleActivateVersion: (id: string) => void;
  handleReleaseVersion: (id: string) => void;
  handleDeleteVersion: (id: string, name: string) => void;
  handleDeleteTodo: (todoId: string, todoTitle: string, versionId: string) => void;
  setCreateForVersion: (id: string) => void;
  navigate: (path: string) => void;
}

export function TodosTab({
  versions,
  versionTodos,
  expandedVersions,
  toggleVersion,
  showNewVersion,
  setShowNewVersion,
  versionName,
  setVersionName,
  versionGoal,
  setVersionGoal,
  versionType,
  setVersionType,
  handleCreateVersion,
  handleActivateVersion,
  handleReleaseVersion,
  handleDeleteVersion,
  handleDeleteTodo,
  setCreateForVersion,
  navigate,
}: TodosTabProps) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <GitBranch size={13} /> 版本 & 需求
        </h2>
        <button
          onClick={() => setShowNewVersion(true)}
          className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-[11px] font-medium text-text-secondary hover:text-text-primary"
        >
          <Plus size={12} /> 新版本
        </button>
      </div>

      {showNewVersion && (
        <div className="mb-3 rounded-lg border border-accent/30 bg-bg-card p-4">
          <div className="mb-3">
            <input
              type="text"
              value={versionGoal}
              onChange={(e) => setVersionGoal(e.target.value)}
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
                onClick={() => setVersionType(t.key)}
                className={`flex-1 rounded-md border px-2 py-1.5 text-center text-[11px] font-medium transition-colors ${
                  versionType === t.key
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
              value={versionName}
              onChange={(e) => setVersionName(e.target.value)}
              placeholder="版本号（留空按类型自动生成）"
              className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowNewVersion(false)} className="rounded-md border border-border px-3 py-1 text-xs text-text-secondary">取消</button>
            <button onClick={handleCreateVersion} className="rounded-md bg-accent px-3 py-1 text-xs text-white hover:bg-accent-hover">创建</button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {versions.length === 0 && !showNewVersion && (
          <p className="rounded-lg border border-border bg-bg-card p-4 text-center text-xs text-text-muted">
            还没有版本。创建一个版本来圈定需求范围。
          </p>
        )}
        {versions.map((v) => {
          const style = VERSION_STATUS_STYLE[v.status];
          const isExpanded = expandedVersions.has(v.id);
          const todos = versionTodos[v.id] || [];
          const stats = v.todo_stats;
          const total = stats?.total ?? 0;
          const done = stats?.done ?? 0;
          const pct = total > 0 ? Math.round((done / total) * 100) : 0;

          return (
            <div key={v.id} className="rounded-lg border border-border bg-bg-card">
              <div className="flex items-center justify-between px-4 py-3">
                <button
                  onClick={() => toggleVersion(v.id)}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                >
                  {isExpanded ? (
                    <ChevronDown size={14} className="flex-shrink-0 text-text-muted" />
                  ) : (
                    <ChevronRight size={14} className="flex-shrink-0 text-text-muted" />
                  )}
                  <span className="text-sm font-medium text-text-primary">{v.name}</span>
                  <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${style.bg}`}>
                    {style.label}
                  </span>
                  {total > 0 && (
                    <span className="text-[10px] text-text-muted">{done}/{total} 完成</span>
                  )}
                </button>
                <div className="ml-3 flex items-center gap-1.5">
                  {v.status !== 'released' && (
                    <button
                      onClick={() => setCreateForVersion(v.id)}
                      className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-accent hover:text-accent"
                    >
                      <Plus size={10} /> 需求
                    </button>
                  )}
                  <ActionMenu items={(() => {
                    const items: ActionMenuItem[] = [];
                    if (v.status === 'planning') {
                      items.push({ label: '开始迭代', icon: <Play size={12} />, onClick: () => handleActivateVersion(v.id) });
                    }
                    if (v.status === 'active') {
                      items.push({ label: '发布版本', icon: <CheckCircle size={12} />, onClick: () => handleReleaseVersion(v.id) });
                    }
                    if (v.status !== 'released') {
                      items.push({ label: '删除版本', icon: <Trash2 size={12} />, danger: true, onClick: () => handleDeleteVersion(v.id, v.name) });
                    }
                    return items;
                  })()} />
                </div>
              </div>

              {total > 0 && (
                <div className="px-4 pb-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border/30">
                      <div
                        className="h-full rounded-full bg-status-done transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-[10px] tabular-nums text-text-muted">{pct}%</span>
                  </div>
                  {stats && (
                    <div className="mt-1 flex gap-3 text-[10px] text-text-muted">
                      {stats.pending > 0 && <span>{stats.pending} 待启动</span>}
                      {stats.active > 0 && <span>{stats.active} 进行中</span>}
                      {stats.done > 0 && <span>{stats.done} 已完成</span>}
                      {stats.error > 0 && <span className="text-status-error">{stats.error} 异常</span>}
                    </div>
                  )}
                </div>
              )}

              {v.goal && isExpanded && (
                <div className="border-t border-border/50 px-4 py-2">
                  <p className="text-xs text-text-secondary">{v.goal}</p>
                </div>
              )}

              {v.status === 'released' && v.changelog && isExpanded && (
                <div className="border-t border-border/50 px-4 py-2">
                  <p className="mb-1 text-[10px] font-medium text-text-tertiary">变更记录</p>
                  <p className="whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">{v.changelog}</p>
                </div>
              )}

              {isExpanded && (
                <div className="border-t border-border/50">
                  {todos.length === 0 ? (
                    <p className="px-4 py-3 text-center text-[11px] text-text-muted">
                      暂无需求，点击"+ 需求"添加
                    </p>
                  ) : (
                    <div className="divide-y divide-border/30">
                      {todos.map((todo) => (
                        <div
                          key={todo.id}
                          onClick={() => navigate(`/todo/${todo.id}`)}
                          className="group flex cursor-pointer items-center gap-3 px-4 py-2.5 transition-colors hover:bg-bg-elevated"
                        >
                          <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${statusDotColor[todo.status]}`} />
                          <span className="min-w-0 flex-1 truncate text-xs text-text-primary">{todo.title}</span>
                          <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${statusBadgeBg[todo.status]}`}>
                            {STATUS_LABELS[todo.status]}
                          </span>
                          {todo.current_phase && <PhaseProgress currentPhase={todo.current_phase} />}
                          <div className="flex flex-shrink-0 gap-1">
                            {todo.tags.slice(0, 2).map((tag) => (
                              <span
                                key={tag.label}
                                className="rounded px-1 py-0.5 text-[9px] font-medium"
                                style={{ backgroundColor: `${tag.color}18`, color: tag.color }}
                              >
                                {tag.label}
                              </span>
                            ))}
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDeleteTodo(todo.id, todo.title, v.id); }}
                            className="flex-shrink-0 rounded p-1 text-text-muted opacity-0 transition-all hover:bg-status-error/10 hover:text-status-error group-hover:opacity-100"
                            title="删除需求"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
