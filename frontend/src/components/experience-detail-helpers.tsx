import type { ReactNode } from 'react';
import type { ExperienceCategory } from '../types/api';

/** decisions/pitfalls 可能是纯字符串，也可能是结构化 dict。统一转为可渲染文本。 */
export function formatListItem(item: unknown): string {
  if (typeof item === 'string') return item;
  if (item && typeof item === 'object') {
    const obj = item as Record<string, unknown>;
    // decisions 格式: {point, chosen, reason, alternatives?}
    if (obj.point) {
      let text = String(obj.point);
      if (obj.chosen) text += ` → ${obj.chosen}`;
      if (obj.reason) text += `（${obj.reason}）`;
      return text;
    }
    // pitfalls 格式: {cause, fix, issue?, prevention?}
    if (obj.cause || obj.fix) {
      const parts: string[] = [];
      if (obj.cause) parts.push(String(obj.cause));
      if (obj.fix) parts.push(`修复: ${obj.fix}`);
      return parts.join(' → ');
    }
    // 兜底：取所有值拼接
    return Object.values(obj).filter(Boolean).map(String).join(' | ');
  }
  return String(item);
}

export const STATUS_STYLE: Record<string, string> = {
  draft: 'bg-amber-500/15 text-amber-600',
  confirmed: 'bg-status-done/15 text-status-done',
  archived: 'bg-text-muted/15 text-text-muted',
};

export const CATEGORY_OPTIONS: { value: ExperienceCategory; label: string }[] = [
  { value: 'technical', label: '技术' },
  { value: 'business_rule', label: '业务规则' },
  { value: 'pitfall', label: '踩坑' },
  { value: 'architecture_decision', label: '架构决策' },
  { value: 'scope_change', label: '范围变更' },
  { value: 'estimation', label: '估算校准' },
];

export function Section({
  icon,
  title,
  variant,
  children,
}: {
  icon: ReactNode;
  title: string;
  variant?: 'warning';
  children: ReactNode;
}) {
  return (
    <div className="mb-5">
      <div className="mb-2 flex items-center gap-1.5">
        <span className={variant === 'warning' ? 'text-status-error' : 'text-accent'}>
          {icon}
        </span>
        <h3 className="text-[11px] font-semibold tracking-wide text-text-tertiary uppercase">
          {title}
        </h3>
      </div>
      <div className="rounded-lg border border-border bg-bg-elevated p-3.5">
        {children}
      </div>
    </div>
  );
}
