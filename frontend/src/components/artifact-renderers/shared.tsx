import type { ReactNode } from 'react';

export function SectionCard({
  icon,
  title,
  children,
  variant = 'default',
}: {
  icon?: ReactNode;
  title: string;
  children: ReactNode;
  variant?: 'default' | 'warning' | 'success' | 'code';
}) {
  const borderMap = {
    default: 'border-border',
    warning: 'border-status-error/20',
    success: 'border-status-done/20',
    code: 'border-accent/20',
  };

  return (
    <div className={`mb-4 rounded-lg border ${borderMap[variant]} bg-bg-elevated`}>
      <div className="flex items-center gap-1.5 border-b border-border/50 px-3.5 py-2">
        {icon && (
          <span className={variant === 'warning' ? 'text-status-error' : 'text-accent'}>
            {icon}
          </span>
        )}
        <h4 className="text-[11px] font-semibold tracking-wide text-text-tertiary uppercase">
          {title}
        </h4>
      </div>
      <div className="px-3.5 py-3">{children}</div>
    </div>
  );
}

export function TextBlock({ children }: { children: ReactNode }) {
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">{children}</p>
  );
}

export function TerminalBlock({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md bg-[#1a1b26] p-3">
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-[#9ece6a]">
        {children}
      </pre>
    </div>
  );
}

export function CodeBlock({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md bg-bg-card p-3">
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-text-secondary">
        {children}
      </pre>
    </div>
  );
}

export function StatusDot({ status }: { status: 'pass' | 'fail' | 'unknown' }) {
  const colorMap = {
    pass: 'bg-status-done',
    fail: 'bg-status-error',
    unknown: 'bg-text-muted',
  };
  return <span className={`inline-block h-2 w-2 rounded-full ${colorMap[status]}`} />;
}

export function Badge({
  children,
  variant = 'default',
}: {
  children: ReactNode;
  variant?: 'default' | 'success' | 'error' | 'warning';
}) {
  const styles = {
    default: 'bg-accent/10 text-accent',
    success: 'bg-status-done/15 text-status-done',
    error: 'bg-status-error/15 text-status-error',
    warning: 'bg-[#E5A93D]/15 text-[#E5A93D]',
  };
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${styles[variant]}`}>
      {children}
    </span>
  );
}

export function NumberedList({ items }: { items: string[] }) {
  return (
    <ol className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-text-secondary">
          <span className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-accent/10 text-[10px] font-medium text-accent">
            {i + 1}
          </span>
          <span className="leading-relaxed">{item}</span>
        </li>
      ))}
    </ol>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-24 items-center justify-center text-xs text-text-muted">{message}</div>
  );
}

export function asString(v: unknown): string {
  if (typeof v === 'string') return v;
  if (v == null) return '';
  return JSON.stringify(v, null, 2);
}

export function asArray(v: unknown): unknown[] {
  if (Array.isArray(v)) return v;
  return [];
}
