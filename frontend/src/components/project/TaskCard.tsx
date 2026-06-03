import { useState, useRef } from 'react';
import { Send, ChevronDown, ChevronRight, ExternalLink, Loader2, AlertCircle, CheckCircle2, Lock, Trash2, RotateCcw } from 'lucide-react';
import type { Todo } from '../../types/api';
import type { TaskState } from '../../hooks/useProjectTaskStream';
import { api } from '../../api/client';

interface TaskCardProps {
  todo: Todo;
  taskState: TaskState;
  navigate: (path: string) => void;
  onDelete?: (todoId: string, todoTitle: string) => void;
  onComplete?: (todoId: string) => void;
  onReopen?: (todoId: string) => void;
}

const STATUS_INDICATOR: Record<string, { color: string; label: string }> = {
  idle: { color: 'bg-text-muted', label: '空闲' },
  running: { color: 'bg-accent animate-pulse', label: '运行中' },
  error: { color: 'bg-status-error', label: '异常' },
};

export function TaskCard({ todo, taskState, navigate, onDelete, onComplete, onReopen }: TaskCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [confirmComplete, setConfirmComplete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const indicator = STATUS_INDICATOR[taskState.status] || STATUS_INDICATOR.idle;
  const isRunning = taskState.status === 'running';
  const isDone = todo.status === 'done';
  const hasContent = taskState.lastContent.length > 0;
  const hasArtifacts = taskState.artifacts.length > 0;

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || sending) return;
    setSending(true);
    setInput('');
    try {
      await api.sendQuickMessage(todo.id, msg);
    } catch {
      // error will come through task stream
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const preview = taskState.lastContent.slice(-200);

  return (
    <div className={`rounded-lg border transition-all ${
      isRunning ? 'border-accent/40 bg-accent/5' :
      taskState.status === 'error' ? 'border-status-error/40 bg-status-error/5' :
      isDone ? 'border-status-done/30 bg-status-done/5' :
      'border-border bg-bg-card'
    }`}>
      {/* Header */}
      <div
        className="flex cursor-pointer items-center gap-3 px-4 py-3"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <ChevronDown size={13} className="text-text-muted" /> : <ChevronRight size={13} className="text-text-muted" />}
        <span className={`h-2 w-2 flex-shrink-0 rounded-full ${indicator.color}`} />
        <span className="min-w-0 flex-1 truncate text-xs font-medium text-text-primary">
          {todo.title}
        </span>
        {isDone && <CheckCircle2 size={13} className="text-status-done" />}
        {isDone && onReopen && (
          <button
            onClick={(e) => { e.stopPropagation(); onReopen(todo.id); }}
            className="flex items-center gap-1 rounded-md border border-amber-500/40 bg-amber-500/15 px-2 py-1 text-[11px] font-medium text-amber-400 hover:bg-amber-500/25 hover:border-amber-500/60 transition-colors"
          >
            <RotateCcw size={11} /> 恢复
          </button>
        )}
        {todo.blocked_by && todo.blocked_by.length > 0 && !isDone && (
          <span className="flex items-center gap-0.5 rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[9px] text-amber-400" title="被阻塞">
            <Lock size={8} /> 阻塞
          </span>
        )}
        {taskState.status === 'error' && <AlertCircle size={13} className="text-status-error" />}
        {isRunning && <Loader2 size={13} className="animate-spin text-accent" />}
        {taskState.stage && (
          <span className="max-w-[160px] truncate text-[10px] text-text-muted">
            {taskState.stage}
          </span>
        )}
      </div>

      {/* AI Content Preview (collapsed) */}
      {!expanded && hasContent && (
        <div className="border-t border-border/30 px-4 py-2">
          <p className="line-clamp-2 text-[11px] leading-relaxed text-text-secondary">
            {preview}
          </p>
          {isRunning && <span className="inline-block h-3 w-1 animate-pulse bg-accent/60" />}
        </div>
      )}

      {/* Expanded Panel */}
      {expanded && (
        <div className="border-t border-border/30">
          {/* Content area */}
          <div className="max-h-48 overflow-y-auto px-4 py-3">
            {hasContent ? (
              <div className="text-xs leading-relaxed text-text-secondary">
                <pre className="whitespace-pre-wrap font-sans">{taskState.lastContent}</pre>
                {isRunning && <span className="inline-block h-3 w-1.5 animate-pulse bg-accent/60" />}
              </div>
            ) : (
              <p className="text-[11px] text-text-muted">
                {isDone ? '任务已完成' : '暂无内容，发送指令启动对话'}
              </p>
            )}
          </div>

          {/* Artifacts */}
          {taskState.artifacts.length > 0 && (
            <div className="border-t border-border/20 px-4 py-2">
              <div className="flex flex-wrap gap-1.5">
                {taskState.artifacts.map((a) => (
                  <span key={a} className="rounded-md bg-status-done/10 px-2 py-0.5 text-[10px] font-medium text-status-done">
                    {a}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Quick Input */}
          {!isDone && (
            <div className="border-t border-border/30 px-4 py-2.5">
              <div className="flex items-center gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="输入快速指令..."
                  className="h-7 flex-1 rounded-md border border-border bg-bg-input px-2.5 text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
                  disabled={sending}
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || sending}
                  className="flex h-7 w-7 items-center justify-center rounded-md bg-accent text-white transition-opacity hover:bg-accent-hover disabled:opacity-30"
                >
                  {sending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                </button>
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="border-t border-border/20 px-4 py-2">
            {/* Confirm complete prompt */}
            {confirmComplete && (
              <div className="mb-2 flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                <AlertCircle size={12} className="flex-shrink-0 text-amber-400" />
                <span className="flex-1 text-[10px] text-amber-300">
                  {!hasArtifacts ? '该需求尚未产出任何交付物，确定标记完成？' : '确定标记该需求为完成？'}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); onComplete!(todo.id); setConfirmComplete(false); }}
                  className="rounded bg-status-done/20 px-2 py-0.5 text-[10px] font-medium text-status-done hover:bg-status-done/30"
                >
                  确认
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmComplete(false); }}
                  className="rounded bg-text-muted/10 px-2 py-0.5 text-[10px] text-text-muted hover:bg-text-muted/20"
                >
                  取消
                </button>
              </div>
            )}

            <div className="flex items-center justify-between">
              <button
                onClick={(e) => { e.stopPropagation(); navigate(`/todo/${todo.id}`); }}
                className="flex items-center gap-1 text-[10px] font-medium text-accent hover:underline"
              >
                查看完整对话 <ExternalLink size={10} />
              </button>
              <div className="flex items-center gap-2">
                {onComplete && !isDone && (todo.status === 'active' || todo.status === 'pending') && !confirmComplete && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setConfirmComplete(true); }}
                    className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-status-done bg-status-done/10 transition-colors hover:bg-status-done/20"
                  >
                    <CheckCircle2 size={10} /> 完成
                  </button>
                )}
                {isDone && onReopen && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onReopen(todo.id); }}
                    className="flex items-center gap-1 rounded-md border border-amber-500/40 bg-amber-500/15 px-2 py-1 text-[11px] font-medium text-amber-400 hover:bg-amber-500/25 hover:border-amber-500/60 transition-colors"
                  >
                    <RotateCcw size={11} /> 恢复
                  </button>
                )}
                {onDelete && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(todo.id, todo.title); }}
                    className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-text-muted transition-colors hover:bg-status-error/10 hover:text-status-error"
                  >
                    <Trash2 size={10} /> 删除
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
