import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus } from 'lucide-react';
import type { TodoStatus, PhaseType } from '../types/api';
import { STATUS_LABELS, PHASE_LABELS, PHASE_ORDER } from '../types/api';
import { useTodos } from '../store/TodoContext';
import CreateTodoModal from '../components/CreateTodoModal';

type TabKey = 'all' | TodoStatus;

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

export default function TodoList() {
  const [activeTab, setActiveTab] = useState<TabKey>('all');
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();
  const { todos, addTodo } = useTodos();

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: 'all', label: '全部', count: todos.length },
    { key: 'pending', label: '待启动', count: todos.filter((t) => t.status === 'pending').length },
    { key: 'active', label: '进行中', count: todos.filter((t) => t.status === 'active').length },
    { key: 'done', label: '已完成', count: todos.filter((t) => t.status === 'done').length },
  ];

  const handleCreate = async (title: string, description: string) => {
    const todo = await addTodo(title, description);
    navigate(`/todo/${todo.id}`);
  };

  const filtered = todos.filter((t) => {
    const matchTab = activeTab === 'all' || t.status === activeTab;
    const matchSearch =
      !search ||
      t.title.toLowerCase().includes(search.toLowerCase()) ||
      t.description?.toLowerCase().includes(search.toLowerCase());
    return matchTab && matchSearch;
  });

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <h1 className="font-heading text-lg font-semibold text-text-primary">任务</h1>
          <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-[11px] font-medium text-accent">
            {todos.length}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search
              size={15}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              placeholder="搜索任务..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-48 rounded-md border border-border bg-bg-input pl-8 pr-3 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
            />
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex h-8 items-center gap-1 rounded-md bg-accent px-3 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
          >
            <Plus size={14} />
            新建
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border px-6 pt-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-t-md px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? 'border-b-2 border-accent text-accent'
                : 'text-text-tertiary hover:text-text-secondary'
            }`}
          >
            {tab.label}
            <span className="ml-1 text-[10px] opacity-60">{tab.count}</span>
          </button>
        ))}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="flex flex-col gap-2">
          {filtered.map((todo) => (
            <div
              key={todo.id}
              onClick={() => navigate(`/todo/${todo.id}`)}
              className="group flex cursor-pointer items-center gap-4 rounded-lg border border-border bg-bg-card px-4 py-3 transition-colors hover:border-accent/30 hover:bg-bg-elevated"
            >
              {/* Status dot */}
              <span className={`h-2 w-2 flex-shrink-0 rounded-full ${statusDotColor[todo.status]}`} />

              {/* Content */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="truncate text-sm font-medium text-text-primary">
                    {todo.title}
                  </h3>
                  <span
                    className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${statusBadgeBg[todo.status]}`}
                  >
                    {STATUS_LABELS[todo.status]}
                  </span>
                </div>
                {todo.description && (
                  <p className="mt-0.5 truncate text-xs text-text-secondary">
                    {todo.description}
                  </p>
                )}
              </div>

              {/* Phase progress indicator */}
              {todo.current_phase && (
                <PhaseProgress currentPhase={todo.current_phase} />
              )}

              {/* Tags */}
              <div className="flex flex-shrink-0 gap-1">
                {todo.tags.map((tag) => (
                  <span
                    key={tag.label}
                    className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                    style={{
                      backgroundColor: `${tag.color}18`,
                      color: tag.color,
                    }}
                  >
                    {tag.label}
                  </span>
                ))}
              </div>

              {/* Date */}
              <span className="flex-shrink-0 text-[10px] text-text-muted">{todo.created_at}</span>
            </div>
          ))}
        </div>
      </div>

      <CreateTodoModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}

function PhaseProgress({ currentPhase }: { currentPhase: PhaseType }) {
  const currentIdx = PHASE_ORDER.indexOf(currentPhase);

  return (
    <div className="flex flex-shrink-0 items-center gap-0.5" title={`当前: ${PHASE_LABELS[currentPhase]}`}>
      {PHASE_ORDER.map((pt, i) => (
        <div
          key={pt}
          className={`h-1 w-2.5 rounded-full transition-colors ${
            i < currentIdx
              ? 'bg-status-done'
              : i === currentIdx
              ? 'bg-accent'
              : 'bg-border'
          }`}
        />
      ))}
      <span className="ml-1.5 text-[9px] text-text-muted">{PHASE_LABELS[currentPhase]}</span>
    </div>
  );
}
