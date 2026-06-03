import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'warning';
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = '确认',
  cancelLabel = '取消',
  variant = 'default',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  const isWarning = variant === 'warning';

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />
      <div className="relative mx-4 w-full max-w-[400px] animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
        <div className="px-5 py-5">
          {/* Icon + Title */}
          <div className="flex items-start gap-3">
            <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${
              isWarning ? 'bg-amber-100 text-amber-600' : 'bg-accent/10 text-accent'
            }`}>
              {isWarning ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
            </div>
            <div className="min-w-0 pt-0.5">
              <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">{message}</p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3.5">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded-md border border-border px-3.5 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`flex items-center gap-1.5 rounded-md px-4 py-1.5 text-xs font-medium text-white transition-colors disabled:opacity-50 ${
              isWarning
                ? 'bg-amber-500 hover:bg-amber-600'
                : 'bg-accent hover:bg-accent-hover'
            }`}
          >
            {loading && <Loader2 size={12} className="animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
