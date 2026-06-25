import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Trash2, Info } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────

type ConfirmVariant = 'default' | 'warning' | 'danger' | 'info';

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ConfirmVariant;
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

// ── Context ───────────────────────────────────────────────

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

export function useConfirm(): (options: ConfirmOptions) => Promise<boolean> {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used within ConfirmProvider');
  return ctx.confirm;
}

// ── Provider ──────────────────────────────────────────────

interface DialogState extends ConfirmOptions {
  open: boolean;
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DialogState>({
    open: false,
    title: '',
    message: '',
  });
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    setState({ ...options, open: true });
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const handleConfirm = () => {
    setState(s => ({ ...s, open: false }));
    resolverRef.current?.(true);
    resolverRef.current = null;
  };

  const handleCancel = () => {
    setState(s => ({ ...s, open: false }));
    resolverRef.current?.(false);
    resolverRef.current = null;
  };

  const variant = state.variant || 'default';

  const VARIANT_CONFIG = {
    default: { icon: CheckCircle2, iconBg: 'bg-accent/10 text-accent', btnBg: 'bg-accent hover:bg-accent-hover' },
    warning: { icon: AlertTriangle, iconBg: 'bg-amber-500/10 text-amber-500', btnBg: 'bg-amber-500 hover:bg-amber-600' },
    danger: { icon: Trash2, iconBg: 'bg-red-500/10 text-red-500', btnBg: 'bg-red-500 hover:bg-red-600' },
    info: { icon: Info, iconBg: 'bg-blue-500/10 text-blue-500', btnBg: 'bg-blue-500 hover:bg-blue-600' },
  };

  const config = VARIANT_CONFIG[variant];
  const Icon = config.icon;

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}

      {/* Dialog overlay */}
      {state.open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-[2px] animate-fade-in"
            onClick={handleCancel}
          />

          {/* Dialog */}
          <div className="relative mx-4 w-full max-w-[400px] animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
            <div className="px-5 py-5">
              <div className="flex items-start gap-3">
                <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${config.iconBg}`}>
                  <Icon size={18} />
                </div>
                <div className="min-w-0 pt-0.5">
                  <h3 className="text-sm font-semibold text-text-primary">{state.title}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">{state.message}</p>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3.5">
              <button
                onClick={handleCancel}
                className="rounded-md border border-border px-3.5 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
              >
                {state.cancelLabel || '取消'}
              </button>
              <button
                onClick={handleConfirm}
                className={`flex items-center gap-1.5 rounded-md px-4 py-1.5 text-xs font-medium text-white transition-colors ${config.btnBg}`}
              >
                {state.confirmLabel || '确认'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}
