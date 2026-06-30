import { useState, useEffect } from 'react';
import { X, Lightbulb, Clock } from 'lucide-react';
import { api } from '../api/client';
import { useToast } from './Toast';
import type { Experience, ExperienceCategory } from '../types/api';
import { EXPERIENCE_STATUS_LABELS } from '../types/api';
import { STATUS_STYLE } from './experience-detail-helpers';
import { ExperienceDetailBody, type ExperienceFormValues } from './ExperienceDetailBody';
import { ExperienceDetailFooter, type ExperienceDetailActions } from './ExperienceDetailFooter';

interface Props {
  experience: Experience | null;
  onClose: () => void;
  onAction?: () => void;
}

export default function ExperienceDetailModal({ experience, onClose, onAction }: Props) {
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  const [distilling, setDistilling] = useState(false);
  const [form, setForm] = useState<ExperienceFormValues>({
    title: '',
    problem: '',
    solution: '',
    decisions: [],
    pitfalls: [],
    applicable_scenarios: '',
    category: 'technical' as ExperienceCategory,
    half_life_days: 180,
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
      category: experience.category,
      half_life_days: experience.half_life_days,
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

  const handleDistill = async () => {
    setDistilling(true);
    try {
      await api.distillExperience(experience.id);
      toast('已提炼为个人经验', 'success');
      onAction?.();
    } catch {
      toast('提炼失败', 'error');
    } finally {
      setDistilling(false);
    }
  };

  const actions: ExperienceDetailActions = {
    onClose,
    onEdit: () => setEditing(true),
    onCancel: () => setEditing(false),
    onSave: handleSave,
    onConfirm: handleConfirm,
    onArchive: handleArchive,
    onPromote: handlePromote,
    onDistill: handleDistill,
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
            <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${STATUS_STYLE[experience.status] || ''}`}>
              {EXPERIENCE_STATUS_LABELS[experience.status as keyof typeof EXPERIENCE_STATUS_LABELS] || experience.status}
            </span>
            {experience.is_stale && (
              <span className="flex items-center gap-0.5 rounded-full bg-status-error/15 px-1.5 py-0.5 text-[9px] font-medium text-status-error">
                <Clock size={9} /> 过期
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary"
          >
            <X size={14} />
          </button>
        </div>

        <ExperienceDetailBody
          experience={experience}
          form={form}
          setForm={setForm}
          editing={editing}
        />

        <ExperienceDetailFooter
          experience={experience}
          editing={editing}
          distilling={distilling}
          actions={actions}
        />
      </div>
    </div>
  );
}
