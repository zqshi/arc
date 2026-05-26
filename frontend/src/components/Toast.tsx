import { useState, useCallback, useEffect, createContext, useContext, type ReactNode } from 'react';
import { quotaEvents } from '../lib/quota-events';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastMessage {
  id: number;
  text: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (text: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([]);

  const toast = useCallback((text: string, type: ToastType = 'info') => {
    const id = nextId++;
    setMessages((prev) => [...prev, { id, text, type }]);
    setTimeout(() => {
      setMessages((prev) => prev.filter((m) => m.id !== id));
    }, type === 'warning' ? 6000 : 4000);
  }, []);

  useEffect(() => {
    return quotaEvents.on((detail) => {
      toast(detail, 'warning');
    });
  }, [toast]);

  const typeStyles: Record<string, string> = {
    success: 'border-status-done/40 bg-status-done/10 text-status-done',
    error: 'border-status-error/40 bg-status-error/10 text-status-error',
    info: 'border-accent/40 bg-accent/10 text-accent',
    warning: 'border-amber-400/40 bg-amber-400/10 text-amber-500',
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2" aria-live="polite" aria-relevant="additions">
        {messages.map((msg) => (
          <div
            key={msg.id}
            role={msg.type === 'error' || msg.type === 'warning' ? 'alert' : 'status'}
            className={`animate-in slide-in-from-right rounded-lg border px-4 py-2.5 text-xs font-medium shadow-lg backdrop-blur-sm ${typeStyles[msg.type]}`}
          >
            {msg.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
