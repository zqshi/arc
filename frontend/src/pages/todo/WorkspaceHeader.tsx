import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Lock, Menu, MessageSquare } from 'lucide-react';
import type { Todo } from '../../types/api';
import { STATUS_LABELS } from '../../types/api';

export function WorkspaceHeader({ todo, isCompact, hasSidebar, onOpenSidebar }: {
  todo: Todo; isCompact: boolean; hasSidebar: boolean; onOpenSidebar: () => void;
}) {
  const navigate = useNavigate();
  return (
    <header className="flex items-center gap-2.5 border-b border-border px-4 py-2.5">
      {isCompact && hasSidebar && (
        <button onClick={onOpenSidebar} className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-bg-elevated hover:text-text-primary">
          <Menu size={14} />
        </button>
      )}
      {isCompact && !hasSidebar && (
        <button
          onClick={() => todo.project_id ? navigate(`/project/${todo.project_id}`) : navigate('/')}
          className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-bg-elevated hover:text-text-primary"
        >
          <ChevronLeft size={14} />
        </button>
      )}
      <h1 className="min-w-0 flex-1 truncate text-xs font-semibold text-text-primary">{todo.title}</h1>
      {todo.blocked_by && todo.blocked_by.length > 0 && (
        <span className="flex items-center gap-0.5 rounded-full bg-amber-500/10 px-2 py-0.5 text-[9px] font-medium text-amber-400" title={`被 ${todo.blocked_by.length} 个需求阻塞`}>
          <Lock size={8} /> 阻塞
        </span>
      )}
      <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
        todo.status === 'active' ? 'bg-accent/15 text-accent'
          : todo.status === 'done' ? 'bg-status-done/15 text-status-done'
          : todo.status === 'error' ? 'bg-status-error/15 text-status-error'
          : 'bg-text-muted/15 text-text-muted'
      }`}>
        {STATUS_LABELS[todo.status]}
      </span>
      {todo.execution_mode === 'conversation' && (
        <span className="rounded-full bg-purple-500/10 px-1.5 py-0.5 text-[9px] font-medium text-purple-400">
          <MessageSquare size={8} className="mr-0.5 inline" /> 对话
        </span>
      )}
    </header>
  );
}
