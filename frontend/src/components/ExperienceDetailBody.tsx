import type { Dispatch, SetStateAction } from 'react';
import { Target, Lightbulb, BookOpen, AlertTriangle } from 'lucide-react';
import type { Experience, ExperienceCategory } from '../types/api';
import { EXPERIENCE_CATEGORY_LABELS } from '../types/api';
import { Section, formatListItem, CATEGORY_OPTIONS } from './experience-detail-helpers';

export interface ExperienceFormValues {
  title: string;
  problem: string;
  solution: string;
  decisions: string[];
  pitfalls: string[];
  applicable_scenarios: string;
  category: ExperienceCategory;
  half_life_days: number;
}

interface BodyProps {
  experience: Experience;
  form: ExperienceFormValues;
  setForm: Dispatch<SetStateAction<ExperienceFormValues>>;
  editing: boolean;
}

export function ExperienceDetailBody({ experience, form, setForm, editing }: BodyProps) {
  return (
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
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium bg-blue-500/15 text-blue-500`}>
            {EXPERIENCE_CATEGORY_LABELS[experience.category] || experience.category}
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
          复用 {experience.reuse_count} 次 · 信心 {Math.round(experience.confidence * 100)}% · 半衰期 {experience.half_life_days} 天
        </span>
      </div>

      {editing && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-[10px] font-medium text-text-muted">类型</label>
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value as ExperienceCategory })}
              className="h-8 w-full rounded border border-border bg-bg-input px-2 text-xs text-text-primary focus:border-border-active focus:outline-none"
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[10px] font-medium text-text-muted">半衰期（天）</label>
            <input
              type="number"
              min={1}
              value={form.half_life_days}
              onChange={(e) => setForm({ ...form, half_life_days: parseInt(e.target.value) || 180 })}
              className="h-8 w-full rounded border border-border bg-bg-input px-2 text-xs text-text-primary focus:border-border-active focus:outline-none"
            />
          </div>
        </div>
      )}

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
              value={form.decisions.map(formatListItem).join('\n')}
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
                  <span className="leading-relaxed">{formatListItem(d)}</span>
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
              value={form.pitfalls.map(formatListItem).join('\n')}
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
                  <span className="leading-relaxed">{formatListItem(p)}</span>
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

      {experience.source_experience_id && (
        <div className="mb-4 rounded-md border border-border bg-bg-elevated px-3 py-2 text-[10px] text-text-muted">
          由项目经验提炼而来
        </div>
      )}
    </div>
  );
}
