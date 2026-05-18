import { useState, useEffect } from 'react';
import { X, AlertTriangle, Lightbulb, Target, BookOpen, Pencil, Check, Archive, ArrowUpRight } from 'lucide-react';
import { api } from '../api/client';
import { useToast } from './Toast';
import type { Experience } from '../types/api';
import { EXPERIENCE_STATUS_LABELS } from '../types/api';

interface Props {
  experience: Experience | null;
  onClose: () => void;
  onAction?: () => void;
}

export default function ExperienceDetailModal({ experience, onClose, onAction }: Props) {
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    title: '',
    problem: '',
    solution: '',
    decisions: [] as string[],
    pitfalls: [] as string[],
    applicable_scenarios: '',
  });

  useEffect(() => {
    if (!experience) return;
    setEditing(false);
    setForm({
      title: experience.title,
      problem: experience.problem,
      solution: experience.solution,
      decisions: [...experience.decisions],
      pitfalls: [...experience.pitfalls],
      applicable_scenarios: experience.applicable_scenarios || '',
    });
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [experience, onClose]);

  if (!experience) return null;

  const handleSave = async () => {
    try {
      await api.updateExperience(experience.id, form);
      setEditing(false);
      toast('已保存', 'success');
      onAction?.();
    } catch {
      toast('保存失败', 'error');
    }
  };

  const handleConfirm = async () => {
    try {
      await api.confirmExperience(experience.id);
      toast('已确认', 'success');
      onAction?.();
    } catch {
      toast('确认失败', 'error');
    }
  };

  const handleArchive = async () => {
    try {
      await api.archiveExperience(experience.id);
      toast('已归档', 'success');
      onAction?.();
    } catch {
      toast('归档失败', 'error');
    }
  };

  const handlePromote = async () => {
    try {
      await api.promoteExperience(experience.id);
      toast('已升级为个人经验', 'success');
      onAction?.();
    } catch {
      toast('升级失败', 'error');
    }
  };

  const statusStyle: Record<string, string> = {
    draft: 'bg-amber-500/15 text-amber-600',
    confirmed: 'bg-status-done/15 text-status-done',
    archived: 'bg-text-muted/15 text-text-muted',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative flex max-h-[85vh] w-[640px] flex-col rounded-xl border border-border-active bg-bg-card shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div className="flex items-center gap-2">
            <Lightbulb size={14} className="text-accent" />
            {editing ? (
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-80 rounded border border-border bg-bg-input px-2 py-1 text-sm font-semibold text-text-primary focus:border-border-active focus:outline-none"
              />
            ) : (
              <h2 className="font-heading text-sm font-semibold text-text-primary">
                {experience.title}
              </h2>
            )}
            <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${statusStyle[experience.status] || ''}`}>
              {EXPERIENCE_STATUS_LABELS[experience.status as keyof typeof EXPERIENCE_STATUS_LABELS] || experience.status}
            </span>
          </div>
          <button
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary"
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex flex-wrap gap-1.5">
              <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                experience.scope === 'personal'
                  ? 'bg-purple-500/15 text-purple-500'
                  : 'bg-sky-500/15 text-sky-400'
              }`}>
                {experience.scope === 'personal' ? '个人' : '项目'}
              </span>
              {experience.tags.map((tag) => (
                <span
                  key={tag.label}
                  className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                  style={{ backgroundColor: `${tag.color}18`, color: tag.color }}
                >
                  {tag.label}
                </span>
              ))}
            </div>
            <span className="text-[10px] text-text-muted">
              复用 {experience.reuse_count} 次 · 信心 {Math.round(experience.confidence * 100)}%
            </span>
          </div>

          {/* Problem */}
          <Section icon={<Target size={13} />} title="问题">
            {editing ? (
              <textarea
                value={form.problem}
                onChange={(e) => setForm({ ...form, problem: e.target.value })}
                rows={3}
                className="w-full resize-none rounded border border-border bg-bg-input px-3 py-2 text-sm text-text-primary focus:border-border-active focus:outline-none"
              />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
                {experience.problem}
              </p>
            )}
          </Section>

          {/* Solution */}
          <Section icon={<Lightbulb size={13} />} title="解决方案">
            {editing ? (
              <textarea
                value={form.solution}
                onChange={(e) => setForm({ ...form, solution: e.target.value })}
                rows={4}
                className="w-full resize-none rounded border border-border bg-bg-input px-3 py-2 text-sm text-text-primary focus:border-border-active focus:outline-none"
              />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
                {experience.solution}
              </p>
            )}
          </Section>

          {/* Decisions */}
          {(experience.decisions.length > 0 || editing) && (
            <Section icon={<BookOpen size={13} />} title="关键决策">
              {editing ? (
                <textarea
                  value={form.decisions.join('\n')}
                  onChange={(e) => setForm({ ...form, decisions: e.target.value.split('\n').filter(Boolean) })}
                  rows={3}
                  placeholder="每行一条决策"
                  className="w-full resize-none rounded border border-border bg-bg-input px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                />
              ) : (
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
              )}
            </Section>
          )}

          {/* Pitfalls */}
          {(experience.pitfalls.length > 0 || editing) && (
            <Section icon={<AlertTriangle size={13} />} title="踩坑记录" variant="warning">
              {editing ? (
                <textarea
                  value={form.pitfalls.join('\n')}
                  onChange={(e) => setForm({ ...form, pitfalls: e.target.value.split('\n').filter(Boolean) })}
                  rows={3}
                  placeholder="每行一条踩坑记录"
                  className="w-full resize-none rounded border border-border bg-bg-input px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                />
              ) : (
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
              )}
            </Section>
          )}

          {/* Applicable scenarios */}
          {(experience.applicable_scenarios || editing) && (
            <Section icon={<Target size={13} />} title="适用场景">
              {editing ? (
                <textarea
                  value={form.applicable_scenarios}
                  onChange={(e) => setForm({ ...form, applicable_scenarios: e.target.value })}
                  rows={2}
                  className="w-full resize-none rounded border border-border bg-bg-input px-3 py-2 text-sm text-text-primary focus:border-border-active focus:outline-none"
                />
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
                  {experience.applicable_scenarios}
                </p>
              )}
            </Section>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-5 py-3">
          <span className="text-[10px] text-text-muted">
            创建于 {new Date(experience.created_at).toLocaleDateString('zh-CN')}
          </span>
          <div className="flex items-center gap-2">
            {editing ? (
              <>
                <button
                  onClick={() => setEditing(false)}
                  className="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary"
                >
                  取消
                </button>
                <button
                  onClick={handleSave}
                  className="rounded-md bg-accent px-3 py-1.5 text-xs text-white hover:bg-accent-hover"
                >
                  保存
                </button>
              </>
            ) : (
              <>
                {experience.status !== 'archived' && (
                  <button
                    onClick={() => setEditing(true)}
                    className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary hover:text-text-primary"
                  >
                    <Pencil size={11} /> 编辑
                  </button>
                )}
                {experience.status === 'draft' && (
                  <button
                    onClick={handleConfirm}
                    className="flex items-center gap-1 rounded-md border border-status-done/30 px-2.5 py-1.5 text-xs text-status-done hover:bg-status-done/10"
                  >
                    <Check size={11} /> 确认
                  </button>
                )}
                {experience.status !== 'archived' && (
                  <button
                    onClick={handleArchive}
                    className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-muted hover:text-text-secondary"
                  >
                    <Archive size={11} /> 归档
                  </button>
                )}
                {experience.scope === 'project' && experience.status === 'confirmed' && (
                  <button
                    onClick={handlePromote}
                    className="flex items-center gap-1 rounded-md border border-purple-500/30 px-2.5 py-1.5 text-xs text-purple-500 hover:bg-purple-500/10"
                  >
                    <ArrowUpRight size={11} /> 升级为个人
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary"
                >
                  关闭
                </button>
              </>
            )}
          </div>
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
