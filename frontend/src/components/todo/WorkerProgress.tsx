import { useMemo } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Zap } from 'lucide-react';

export interface WorkerInfo {
  id: string;
  description: string;
  task_type: string;
  status: 'pending' | 'running' | 'done' | 'error';
  output_preview?: string;
  tokens_used?: number;
  elapsed_ms?: number;
}

interface WorkerProgressProps {
  workers: WorkerInfo[];
  planId?: string;
  phase?: 'working' | 'synthesizing' | 'complete';
}

const TYPE_LABELS: Record<string, string> = {
  read_analysis: '代码分析',
  code_search: '代码搜索',
  file_write: '文件编辑',
  command_exec: '命令执行',
  synthesis: '综合分析',
};

/**
 * Displays multi-agent worker progress during orchestrated execution.
 * Shows each worker as a compact card with status and optional output preview.
 */
export function WorkerProgress({ workers, phase }: WorkerProgressProps) {
  const { done, total } = useMemo(() => ({
    done: workers.filter(w => w.status === 'done' || w.status === 'error').length,
    total: workers.length,
  }), [workers]);

  if (workers.length === 0) return null;

  return (
    <div className="mt-2 rounded-lg border border-accent/20 bg-accent/[0.02] p-3">
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap size={13} className="text-accent" />
          <span className="text-[11px] font-semibold text-accent">
            多 Agent 并行
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-text-muted">
          {phase === 'synthesizing' ? (
            <span className="flex items-center gap-1 text-accent">
              <Loader2 size={10} className="animate-spin" /> 综合中...
            </span>
          ) : phase === 'complete' ? (
            <span className="text-status-done">✓ 完成</span>
          ) : (
            <span>{done}/{total} 完成</span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-2 h-1 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${total > 0 ? (done / total) * 100 : 0}%` }}
        />
      </div>

      {/* Worker grid */}
      <div className="grid gap-1.5" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
        {workers.map(w => (
          <div
            key={w.id}
            className={`flex items-start gap-2 rounded-md px-2.5 py-1.5 text-[11px] ${
              w.status === 'running' ? 'bg-accent/5 border border-accent/20' :
              w.status === 'error' ? 'bg-status-error/5 border border-status-error/20' :
              w.status === 'done' ? 'bg-bg-elevated border border-border/50' :
              'bg-bg-primary border border-border/30'
            }`}
          >
            <span className="mt-0.5 flex-shrink-0">
              {w.status === 'running' ? <Loader2 size={11} className="animate-spin text-accent" /> :
               w.status === 'error' ? <AlertCircle size={11} className="text-status-error" /> :
               w.status === 'done' ? <CheckCircle2 size={11} className="text-status-done" /> :
               <span className="block h-2.5 w-2.5 rounded-full border border-text-muted" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="font-medium text-text-primary truncate">{w.description}</span>
              </div>
              <div className="flex items-center gap-2 text-[9px] text-text-muted">
                <span>{TYPE_LABELS[w.task_type] || w.task_type}</span>
                {w.tokens_used != null && w.tokens_used > 0 && (
                  <span>{w.tokens_used} tokens</span>
                )}
                {w.elapsed_ms != null && w.elapsed_ms > 0 && (
                  <span>{(w.elapsed_ms / 1000).toFixed(1)}s</span>
                )}
              </div>
              {w.output_preview && w.status === 'done' && (
                <details className="mt-0.5">
                  <summary className="cursor-pointer text-[9px] text-text-muted hover:text-text-secondary">查看结果</summary>
                  <pre className="mt-0.5 max-h-20 overflow-auto rounded bg-bg-primary p-1.5 text-[9px] text-text-secondary whitespace-pre-wrap">{w.output_preview}</pre>
                </details>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
