import {
  Plus, Play, CheckCircle, ChevronDown, ChevronRight, Trash2, Sparkles, RotateCw,
} from 'lucide-react';
import type { Version, Todo, PlanningSession } from '../../types/api';
import ActionMenu from '../ActionMenu';
import type { ActionMenuItem } from '../ActionMenu';
import { VersionPlanningPanel } from './VersionPlanningPanel';
import { TodoList, ConversationTodoList } from './TodoListItems';
import type { TaskState } from '../../hooks/useProjectTaskStream';
import { VERSION_STATUS_STYLE, type VersionActions, type TodoActions } from './todos-tab-parts';

/** 单个版本行 (展开/折叠 + todos) */
export function VersionRow({
  v,
  isExpanded,
  todos,
  toggleVersion,
  projectId,
  navigate,
  onRefreshData,
  onPreviewRoadmap,
  versionActions,
  todoActions,
  canWrite,
  isConversationMode,
  getTaskState,
  onBatchStart,
  batchStarting,
  setBatchStarting,
}: {
  v: Version;
  isExpanded: boolean;
  todos: Todo[];
  toggleVersion: (id: string) => void;
  projectId: string;
  navigate: (path: string) => void;
  onRefreshData: () => void;
  onPreviewRoadmap?: (session: PlanningSession) => void;
  versionActions: VersionActions;
  todoActions: TodoActions;
  canWrite: boolean;
  isConversationMode: boolean;
  getTaskState?: (todoId: string) => TaskState;
  onBatchStart?: (todoIds: string[]) => Promise<void>;
  batchStarting: boolean;
  setBatchStarting: (v: boolean | ((prev: boolean) => boolean)) => void;
}) {
  const style = VERSION_STATUS_STYLE[v.status];
  const stats = v.todo_stats;
  const total = stats?.total ?? 0;
  const done = stats?.done ?? 0;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="rounded-lg border border-border bg-bg-card">
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
          <span className="rounded bg-bg-elevated px-1.5 py-0.5 font-mono text-[11px] text-text-secondary">{v.name}</span>
          {v.goal && <span className="truncate text-sm font-medium text-text-primary">{v.goal}</span>}
          <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${style.bg}`}>
            {style.label}
          </span>
          {total > 0 && (
            <span className="flex-shrink-0 text-[10px] text-text-muted">{done}/{total}</span>
          )}
        </button>
        <div className="ml-3 flex items-center gap-1.5">
          {canWrite && v.status !== 'released' && (
            <button
              onClick={() => versionActions.setCreateForVersion(v.id)}
              className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-accent hover:text-accent"
            >
              <Plus size={10} /> 需求
            </button>
          )}
          {canWrite && v.status === 'planning' && (
            <button
              onClick={() => versionActions.activate(v.id)}
              className="flex items-center gap-1 rounded-md bg-accent/10 border border-accent/30 px-2 py-1 text-[10px] font-medium text-accent hover:bg-accent/20"
            >
              <Play size={10} /> 开始迭代
            </button>
          )}
          {canWrite && v.status === 'active' && done === total && total > 0 && (
            <button
              onClick={() => versionActions.release(v.id)}
              className="flex items-center gap-1 rounded-md bg-status-done/10 border border-status-done/30 px-2 py-1 text-[10px] font-medium text-status-done hover:bg-status-done/20"
            >
              <CheckCircle size={10} /> 发布版本
            </button>
          )}
          {canWrite && v.status === 'active' && versionActions.analyze && (
            (() => {
              const hasAnalysis = v.has_analysis;
              const isStale = v.analysis_stale;
              // 三态：无分析 / 有分析无变更 / 有分析已变更
              const label = !hasAnalysis ? 'AI 分析' : isStale ? '重新分析' : '查看报告';
              const style = !hasAnalysis
                ? 'border-accent/40 text-accent hover:bg-accent/10'
                : isStale
                ? 'border-amber-500/40 text-amber-600 hover:bg-amber-500/10'
                : 'border-border text-text-secondary hover:border-accent hover:text-accent';
              const Icon = isStale ? RotateCw : Sparkles;
              return (
                <button
                  onClick={() => versionActions.analyze?.(v.id)}
                  className={`flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition-colors ${style}`}
                >
                  <Icon size={10} /> {label}
                </button>
              );
            })()
          )}
          <ActionMenu items={(() => {
            const items: ActionMenuItem[] = [];
            if (v.status !== 'released') {
              items.push({ label: '删除版本', icon: <Trash2 size={12} />, danger: true, onClick: () => versionActions.remove(v.id, v.name) });
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

      {v.status === 'released' && v.changelog && isExpanded && (
        <div className="border-t border-border/50 px-4 py-2">
          <p className="mb-1 text-[10px] font-medium text-text-tertiary">变更记录</p>
          <p className="whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">{v.changelog}</p>
        </div>
      )}

      {/* Version planning workspace (planning status) */}
      {isExpanded && v.status === 'planning' && (
        <div className="border-t border-border/50">
          <VersionPlanningPanel
            projectId={projectId}
            versionId={v.id}
            onTodosCreated={onRefreshData}
            onPreviewRoadmap={onPreviewRoadmap}
          />
          {/* Also show existing todos if any */}
          {todos.length > 0 && (
            <div className="border-t border-border/50">
              <TodoList
                todos={todos}
                versionId={v.id}
                navigate={navigate}
                handleDeleteTodo={todoActions.delete}
              />
            </div>
          )}
        </div>
      )}

      {/* Todo list (active/released status) */}
      {isExpanded && v.status !== 'planning' && (
        <div className="border-t border-border/50">
          {todos.length === 0 ? (
            <p className="px-4 py-3 text-center text-[11px] text-text-muted">
              暂无需求，点击"+ 需求"添加
            </p>
          ) : isConversationMode && getTaskState ? (
            <ConversationTodoList
              todos={todos}
              getTaskState={getTaskState}
              navigate={navigate}
              onBatchStart={onBatchStart}
              batchStarting={batchStarting}
              setBatchStarting={setBatchStarting}
              handleDeleteTodo={todoActions.delete}
              handleCompleteTodo={todoActions.complete}
              handleReopenTodo={todoActions.reopen}
              versionId={v.id}
            />
          ) : (
            <TodoList
              todos={todos}
              versionId={v.id}
              navigate={navigate}
              handleDeleteTodo={todoActions.delete}
              handleCompleteTodo={todoActions.complete}
              handleReopenTodo={todoActions.reopen}
            />
          )}
        </div>
      )}
    </div>
  );
}
