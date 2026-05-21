import { useNavigate } from 'react-router-dom';
import { ArrowLeft, MessageSquare, GitBranch } from 'lucide-react';
import type { Todo } from '../../types/api';
import { STATUS_LABELS } from '../../types/api';

const statusDotColor: Record<string, string> = {
  pending: 'bg-status-pending',
  active: 'bg-accent',
  done: 'bg-status-done',
  error: 'bg-status-error',
  abandoned: 'bg-text-muted',
};

interface TodoSidebarProps {
  todos: Todo[];
  activeTodoId: string;
  projectName?: string;
  versionName?: string;
  projectId?: string;
}

export function TodoSidebar({ todos, activeTodoId, projectName, versionName, projectId }: TodoSidebarProps) {
  const navigate = useNavigate();

  return (
    <div className="flex h-full flex-col border-r border-border bg-bg-sidebar">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-3">
        <button
          onClick={() => projectId ? navigate(`/project/${projectId}`) : navigate('/')}
          className="flex h-6 w-6 items-center justify-center rounded text-text-muted transition-colors hover:bg-bg-elevated hover:text-text-primary"
        >
          <ArrowLeft size={14} />
        </button>
        <div className="min-w-0 flex-1">
          {projectName && (
            <button
              onClick={() => navigate(`/project/${projectId}`)}
              className="block truncate text-[11px] font-medium text-text-primary transition-colors hover:text-accent"
            >
              {projectName}
            </button>
          )}
          {versionName && (
            <span className="block truncate text-[10px] text-text-muted">{versionName}</span>
          )}
        </div>
      </div>

      {/* Todo List */}
      <div className="flex-1 overflow-y-auto py-1">
        {todos.map((todo) => {
          const isActive = todo.id === activeTodoId;
          return (
            <button
              key={todo.id}
              onClick={() => navigate(`/todo/${todo.id}`)}
              className={`flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors ${
                isActive
                  ? 'bg-accent/10 border-l-2 border-accent'
                  : 'border-l-2 border-transparent hover:bg-bg-elevated'
              }`}
            >
              {/* Status dot + attention indicator */}
              <span className="relative flex-shrink-0">
                <span className={`block h-1.5 w-1.5 rounded-full ${statusDotColor[todo.status] || 'bg-text-muted'}`} />
                {todo.needs_attention && (
                  <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-status-error ring-1 ring-bg-sidebar" />
                )}
              </span>

              {/* Title + meta */}
              <div className="min-w-0 flex-1">
                <span className={`block truncate text-[11px] ${
                  isActive ? 'font-medium text-accent' : 'text-text-primary'
                }`}>
                  {todo.title}
                </span>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span className={`text-[9px] ${
                    isActive ? 'text-accent/70' : 'text-text-muted'
                  }`}>
                    {STATUS_LABELS[todo.status]}
                  </span>
                  {todo.execution_mode === 'conversation' ? (
                    <MessageSquare size={8} className="text-purple-400" />
                  ) : (
                    <GitBranch size={8} className="text-text-muted" />
                  )}
                </div>
              </div>
            </button>
          );
        })}

        {todos.length === 0 && (
          <p className="px-3 py-4 text-center text-[11px] text-text-muted">暂无需求</p>
        )}
      </div>
    </div>
  );
}
