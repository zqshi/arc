import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useBreakpoint } from '../hooks/useMediaQuery';
import { api, ApiError } from '../api/client';
import { useCurrentProject } from '../contexts/CurrentProjectContext';
import { TodoSidebar } from '../components/todo';
import { TodoDetailSkeleton } from '../components/Skeleton';
import { WorkspaceHeader } from './todo/WorkspaceHeader';
import { ConversationModeView } from './todo/ConversationModeView';
import { PipelineModeView } from './todo/PipelineModeView';
import type { Todo } from '../types/api';

export default function TodoDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { setProject: setCurrentProject } = useCurrentProject();
  const { isCompact, isNarrow } = useBreakpoint();

  const [todo, setTodo] = useState<Todo | null>(null);
  const [todoLoading, setTodoLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [siblings, setSiblings] = useState<Todo[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const fetchTodo = useCallback(async () => {
    if (!id) return;
    setLoadError(false);
    try {
      const data = await api.getTodo(id);
      setTodo(data);
      if (data.project_id && data.project_name) {
        setCurrentProject({ id: data.project_id, name: data.project_name });
      }
      if (data.project_id && data.version_id) {
        api.listTodos({ project_id: data.project_id, version_id: data.version_id })
          .then((list) => {
            setSiblings(list.map((t) => t.id === id ? { ...t, needs_attention: false } : t));
          }).catch(() => { /* siblings are non-critical */ });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        navigate('/');
      } else {
        setLoadError(true);
      }
    } finally {
      setTodoLoading(false);
    }
  }, [id, navigate, setCurrentProject]);

  useEffect(() => { fetchTodo(); }, [fetchTodo]);
  useEffect(() => () => setCurrentProject(null), [setCurrentProject]);

  if (todoLoading || !todo) {
    if (todoLoading) return <TodoDetailSkeleton />;
    if (loadError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-3 text-text-secondary">
          <p className="text-sm">加载失败，请检查网络后重试</p>
          <button
            onClick={() => { setTodoLoading(true); fetchTodo(); }}
            className="rounded-md bg-accent px-4 py-1.5 text-xs text-white hover:bg-accent-hover"
          >
            重试
          </button>
        </div>
      );
    }
    return (
      <div className="flex h-full items-center justify-center text-text-secondary">
        任务不存在
      </div>
    );
  }

  const hasSidebar = siblings.length > 0;

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left sidebar — todo list */}
      {hasSidebar && !isCompact && (
        <div className={`flex-shrink-0 ${isNarrow ? 'w-[200px]' : 'w-[240px]'}`}>
          <TodoSidebar
            todos={siblings}
            activeTodoId={id!}
            projectName={todo.project_name || undefined}
            versionName={todo.version_name || undefined}
            projectId={todo.project_id || undefined}
          />
        </div>
      )}

      {/* Mobile sidebar drawer */}
      {isCompact && sidebarOpen && hasSidebar && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40" onClick={() => setSidebarOpen(false)} />
          <div className="fixed left-0 top-0 bottom-0 z-50 w-[260px] shadow-xl">
            <TodoSidebar
              todos={siblings}
              activeTodoId={id!}
              projectName={todo.project_name || undefined}
              versionName={todo.version_name || undefined}
              projectId={todo.project_id || undefined}
            />
          </div>
        </>
      )}

      {/* Center + Right content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Compact header bar */}
        <WorkspaceHeader
          todo={todo}
          isCompact={isCompact}
          hasSidebar={hasSidebar}
          onOpenSidebar={() => setSidebarOpen(true)}
        />

        {/* Mode-specific content */}
        {todo.execution_mode === 'conversation' ? (
          <ConversationModeView todo={todo} setTodo={setTodo} isNarrow={isNarrow} isCompact={isCompact} />
        ) : (
          <PipelineModeView todo={todo} setTodo={setTodo} isNarrow={isNarrow} isCompact={isCompact} />
        )}
      </div>
    </div>
  );
}
