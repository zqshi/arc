import { useState } from 'react';
import { Loader2, Plus, CheckSquare, Square } from 'lucide-react';

export interface Suggestion {
  priority: string;
  action: string;
  reason: string;
}

export function SuggestionsPanel({
  suggestions,
  onCreateTodos,
  existingTodoTitles,
}: {
  suggestions: Suggestion[];
  onCreateTodos: (items: Suggestion[]) => Promise<void>;
  existingTodoTitles: Set<string>;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<Set<number>>(new Set());

  const isAlreadyExists = (s: Suggestion) => existingTodoTitles.has(s.action);
  const isDisabled = (i: number) => isAlreadyExists(suggestions[i]) || created.has(i);

  const toggle = (i: number) => {
    if (isDisabled(i)) return;
    const next = new Set(selected);
    if (next.has(i)) next.delete(i); else next.add(i);
    setSelected(next);
  };

  const handleCreate = async () => {
    if (selected.size === 0) return;
    setCreating(true);
    try {
      await onCreateTodos(suggestions.filter((_, i) => selected.has(i)));
      setCreated((prev) => new Set([...prev, ...selected]));
      setSelected(new Set());
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="mt-4 rounded-lg border border-accent/20 bg-accent/5 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-text-primary">行动建议</span>
        <button
          onClick={handleCreate}
          disabled={selected.size === 0 || creating}
          className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-[10px] font-medium text-white hover:bg-accent-hover disabled:opacity-40 transition-colors"
        >
          {creating ? <Loader2 size={10} className="animate-spin" /> : <Plus size={10} />}
          创建为需求 ({selected.size})
        </button>
      </div>
      <div className="space-y-1.5">
        {suggestions.map((s, i) => {
          const disabled = isDisabled(i);
          return (
          <button
            key={i}
            onClick={() => toggle(i)}
            disabled={disabled}
            className={`flex w-full items-start gap-2 rounded-md border px-3 py-2 text-left transition-colors ${
              disabled ? 'opacity-50 cursor-not-allowed border-transparent'
              : selected.has(i) ? 'border-accent/40 bg-accent/10' : 'border-transparent hover:bg-bg-elevated/50'
            }`}
          >
            {disabled
              ? <CheckSquare size={13} className="mt-0.5 flex-shrink-0 text-status-done" />
              : selected.has(i) ? <CheckSquare size={13} className="mt-0.5 flex-shrink-0 text-accent" /> : <Square size={13} className="mt-0.5 flex-shrink-0 text-text-muted" />
            }
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className={`rounded px-1 py-0.5 text-[9px] font-bold ${
                  s.priority === 'P0' ? 'bg-status-error/15 text-status-error' : s.priority === 'P1' ? 'bg-amber-500/15 text-amber-600' : 'bg-text-muted/10 text-text-muted'
                }`}>{s.priority}</span>
                <span className="text-xs font-medium text-text-primary">{s.action}</span>
                {disabled && <span className="text-[9px] text-status-done">已添加</span>}
              </div>
              {s.reason && <p className="mt-0.5 text-[11px] text-text-muted">{s.reason}</p>}
            </div>
          </button>
          );
        })}
      </div>
    </div>
  );
}
