import {
  Play,
  CheckCircle2,
  Trash2,
  RotateCcw,
  Loader2,
  Circle,
  AlertCircle,
  XCircle,
  Rocket,
} from 'lucide-react';
import type { Todo, TodoStatus } from '../../types/api';
import { STATUS_LABELS } from '../../types/api';
import PhaseProgress from '../PhaseProgress';
import { TaskCard } from './TaskCard';
import type { TaskState } from '../../hooks/useProjectTaskStream';

const statusBadgeBg: Record<TodoStatus, string> = {
  pending: 'bg-status-pending/15 text-status-pending',
  active: 'bg-accent/15 text-accent',
  suspended: 'bg-amber-100 text-amber-700',
  done: 'bg-status-done/15 text-status-done',
  error: 'bg-status-error/15 text-status-error',
  abandoned: 'bg-text-muted/15 text-text-muted',
};

export function TodoList({
  todos,
  versionId,
  navigate,
  handleDeleteTodo,
  handleResumeTodo,
  handleCompleteTodo,
}: {
  todos: Todo[];
  versionId: string;
  navigate: (path: string) => void;
  handleDeleteTodo: (todoId: string, todoTitle: string, versionId: string) => void;
  handleResumeTodo?: (todoId: string) => void;
  handleCompleteTodo?: (todoId: string) => void;
}) {
  return (
    <div className="divide-y divide-border/30">
      {todos.map((todo) => {
        const isDone = todo.status === 'done';
        const isAbandoned = todo.status === 'abandoned';
        const dimmed = isDone || isAbandoned;
        const canComplete = todo.status === 'active' || todo.status === 'pending';
        return (
        <div
          key={todo.id}
          onClick={() => navigate(`/todo/${todo.id}`)}
          className={`group flex cursor-pointer items-center gap-3 px-4 py-2.5 transition-colors hover:bg-bg-elevated ${dimmed ? 'opacity-60' : ''}`}
        >
          <span className="relative flex-shrink-0">
            {todo.needs_attention ? (
              <span className="block h-2 w-2 rounded-full bg-accent shadow-[0_0_4px_rgba(74,159,216,0.6)]" />
            ) : (
              <StatusIcon status={todo.status} />
            )}
          </span>
          <span className={`min-w-0 flex-1 truncate text-xs ${isDone ? 'text-text-muted line-through' : isAbandoned ? 'text-text-muted line-through' : 'text-text-primary'}`}>{todo.title}</span>
          <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${statusBadgeBg[todo.status]}`}>
            {STATUS_LABELS[todo.status]}
          </span>
          {todo.execution_mode === 'conversation' && (
            <span className="flex-shrink-0 rounded-full bg-purple-500/10 px-1.5 py-0.5 text-[9px] font-medium text-purple-400">
              对话
            </span>
          )}
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
          {canComplete && handleCompleteTodo && (
            <button
              onClick={(e) => { e.stopPropagation(); handleCompleteTodo(todo.id); }}
              className="flex-shrink-0 flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-status-done bg-status-done/10 hover:bg-status-done/20 opacity-0 group-hover:opacity-100 transition-all"
              title="标记完成"
            >
              <CheckCircle2 size={10} /> 完成
            </button>
          )}
          {todo.status === 'suspended' && handleResumeTodo && (
            <button
              onClick={(e) => { e.stopPropagation(); handleResumeTodo(todo.id); }}
              className="flex-shrink-0 flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-amber-600 bg-amber-50 hover:bg-amber-100 opacity-0 group-hover:opacity-100 transition-all"
              title="恢复需求"
            >
              <RotateCcw size={10} /> 恢复
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); handleDeleteTodo(todo.id, todo.title, versionId); }}
            className="flex-shrink-0 rounded p-1 text-text-muted opacity-0 transition-all hover:bg-status-error/10 hover:text-status-error group-hover:opacity-100"
            title="删除需求"
          >
            <Trash2 size={12} />
          </button>
        </div>
        );
      })}
    </div>
  );
}

export function StatusIcon({ status }: { status: TodoStatus }) {
  switch (status) {
    case 'done':
      return <CheckCircle2 size={14} className="text-status-done" />;
    case 'active':
      return <Play size={14} className="text-accent fill-accent" />;
    case 'error':
      return <AlertCircle size={14} className="text-status-error" />;
    case 'abandoned':
      return <XCircle size={14} className="text-text-muted" />;
    default:
      return <Circle size={14} className="text-text-muted" />;
  }
}

export function ConversationTodoList({
  todos,
  getTaskState,
  navigate,
  onBatchStart,
  batchStarting,
  setBatchStarting,
  handleDeleteTodo,
  handleCompleteTodo,
  handleReopenTodo,
  versionId,
}: {
  todos: Todo[];
  getTaskState: (todoId: string) => TaskState;
  navigate: (path: string) => void;
  onBatchStart?: (todoIds: string[]) => Promise<void>;
  batchStarting: boolean;
  setBatchStarting: (v: boolean) => void;
  handleDeleteTodo: (todoId: string, todoTitle: string, versionId: string) => void;
  handleResumeTodo?: (todoId: string) => void;
  handleCompleteTodo?: (todoId: string) => void;
  handleReopenTodo?: (todoId: string) => void;
  handleReopenTodo?: (todoId: string) => void;
  versionId: string;
}) {
  const pendingTodos = todos.filter((t) => t.status === 'pending');
  const hasPending = pendingTodos.length > 0;

  const handleBatchStart = async () => {
    if (!onBatchStart || batchStarting || !hasPending) return;
    setBatchStarting(true);
    try {
      await onBatchStart(pendingTodos.map((t) => t.id));
    } finally {
      setBatchStarting(false);
    }
  };

  return (
    <div className="p-3 space-y-2">
      {hasPending && onBatchStart && (
        <div className="flex items-center justify-between rounded-md border border-border/50 bg-bg-elevated px-3 py-2">
          <span className="text-[11px] text-text-muted">
            {pendingTodos.length} 个待启动的需求
          </span>
          <button
            onClick={handleBatchStart}
            disabled={batchStarting}
            className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-[11px] font-medium text-white transition-opacity hover:bg-accent-hover disabled:opacity-50"
          >
            {batchStarting ? (
              <><Loader2 size={11} className="animate-spin" /> 启动中...</>
            ) : (
              <><Rocket size={11} /> 全部启动</>
            )}
          </button>
        </div>
      )}

      {todos.map((todo) => (
        <TaskCard
          key={todo.id}
          todo={todo}
          taskState={getTaskState(todo.id)}
          navigate={navigate}
          onDelete={(id, title) => handleDeleteTodo(id, title, versionId)}
          onComplete={handleCompleteTodo}
          onReopen={handleReopenTodo}
        />
      ))}
    </div>
  );
}
