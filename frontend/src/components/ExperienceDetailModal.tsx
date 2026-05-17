import { useEffect } from 'react';
import { X, AlertTriangle, Lightbulb, Target, BookOpen } from 'lucide-react';
import type { Experience } from '../types/api';

interface Props {
  experience: Experience | null;
  onClose: () => void;
}

export default function ExperienceDetailModal({ experience, onClose }: Props) {
  useEffect(() => {
    if (!experience) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [experience, onClose]);

  if (!experience) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative flex max-h-[85vh] w-[640px] flex-col rounded-xl border border-border-active bg-bg-card shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div className="flex items-center gap-2">
            <Lightbulb size={14} className="text-accent" />
            <h2 className="font-heading text-sm font-semibold text-text-primary">
              {experience.title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary"
          >
            <X size={14} />
          </button>
        </div>

        {/* Body - scrollable */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {/* Tags + meta */}
          <div className="mb-4 flex items-center gap-3">
            <div className="flex flex-wrap gap-1.5">
              {experience.scope && experience.scope !== 'todo' && (
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                  experience.scope === 'global'
                    ? 'bg-amber-500/15 text-amber-400'
                    : 'bg-sky-500/15 text-sky-400'
                }`}>
                  {experience.scope === 'global' ? '全局' : '项目'}
                </span>
              )}
              {experience.tags.map((tag) => (
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
            <span className="text-[10px] text-text-muted">
              复用 {experience.reuse_count} 次 · 置信度 {Math.round(experience.confidence * 100)}%
            </span>
          </div>

          {/* Problem */}
          <Section icon={<Target size={13} />} title="问题">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
              {experience.problem}
            </p>
          </Section>

          {/* Solution */}
          <Section icon={<Lightbulb size={13} />} title="解决方案">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
              {experience.solution}
            </p>
          </Section>

          {/* Decisions */}
          {experience.decisions.length > 0 && (
            <Section icon={<BookOpen size={13} />} title="关键决策">
              <ul className="space-y-1.5">
                {experience.decisions.map((d, i) => (
                  <li key={i} className="flex gap-2 text-sm text-text-secondary">
                    <span className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-accent/10 text-[10px] font-medium text-accent">
                      {i + 1}
                    </span>
                    <span className="leading-relaxed">{d}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Pitfalls */}
          {experience.pitfalls.length > 0 && (
            <Section icon={<AlertTriangle size={13} />} title="踩坑记录" variant="warning">
              <ul className="space-y-1.5">
                {experience.pitfalls.map((p, i) => (
                  <li key={i} className="flex gap-2 text-sm text-text-secondary">
                    <span className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-status-error/10 text-[10px] font-medium text-status-error">
                      !
                    </span>
                    <span className="leading-relaxed">{p}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Applicable scenarios */}
          {experience.applicable_scenarios && (
            <Section icon={<Target size={13} />} title="适用场景">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
                {experience.applicable_scenarios}
              </p>
            </Section>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-5 py-3">
          <span className="text-[10px] text-text-muted">
            创建于 {new Date(experience.created_at).toLocaleDateString('zh-CN')}
            {experience.source && ` · 来源: ${experience.source}`}
          </span>
          <button
            onClick={onClose}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:text-text-primary"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  variant,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  variant?: 'warning';
  children: React.ReactNode;
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
