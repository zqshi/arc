import { AlertTriangle } from 'lucide-react';

interface ApprovalDialogProps {
  toolName: string;
  toolInput: Record<string, unknown>;
  requestId: string;
  onRespond: (requestId: string, approved: boolean) => void;
}

/**
 * Modal displayed when sandbox approval gate triggers.
 * Shows the pending mutation (write_file or run_command) and
 * lets the user approve or reject before execution.
 */
export function ApprovalDialog({ toolName, toolInput, requestId, onRespond }: ApprovalDialogProps) {
  const displayContent = toolName === 'run_command'
    ? (toolInput.command as string) || JSON.stringify(toolInput)
    : (toolInput.path as string) || JSON.stringify(toolInput);

  const isCommand = toolName === 'run_command';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-xl border border-border bg-bg-primary p-6 shadow-xl">
        {/* Header */}
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-status-warning/10">
            <AlertTriangle size={20} className="text-status-warning" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">需要确认操作</h3>
            <p className="text-xs text-text-muted">
              AI 请求执行{isCommand ? '命令' : '文件写入'}，请确认是否允许
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="mb-5 rounded-lg border border-border bg-bg-elevated p-4">
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-muted">
            {isCommand ? '命令' : '写入路径'}
          </div>
          <pre className="max-h-40 overflow-auto text-sm text-text-primary whitespace-pre-wrap break-all font-mono">
            {displayContent}
          </pre>
          {!isCommand && !!toolInput.content && (
            <>
              <div className="mt-3 mb-1 text-[10px] font-medium uppercase tracking-wide text-text-muted">
                文件内容预览
              </div>
              <pre className="max-h-32 overflow-auto text-xs text-text-secondary whitespace-pre-wrap font-mono">
                {(toolInput.content as string).slice(0, 500)}
                {(toolInput.content as string).length > 500 ? '\n...(已截断)' : ''}
              </pre>
            </>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            onClick={() => onRespond(requestId, false)}
            className="rounded-lg border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-bg-elevated"
          >
            拒绝
          </button>
          <button
            onClick={() => onRespond(requestId, true)}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90"
          >
            批准执行
          </button>
        </div>
      </div>
    </div>
  );
}
