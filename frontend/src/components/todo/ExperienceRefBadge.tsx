import { useState } from 'react';
import { Lightbulb, ThumbsUp, ThumbsDown, ChevronDown } from 'lucide-react';
import { api } from '../../api/client';
import { useToast } from '../Toast';
import type { ExperienceRef } from '../../types/api';

export function ExperienceRefBadge({ refs, todoId }: { refs: ExperienceRef[]; todoId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, 'up' | 'down'>>({});
  const { toast } = useToast();

  if (!refs || refs.length === 0) return null;

  const handleFeedback = async (expId: string, helpful: boolean) => {
    try {
      await api.feedbackExperience(expId, todoId, helpful);
      setFeedbackGiven((prev) => ({ ...prev, [expId]: helpful ? 'up' : 'down' }));
    } catch {
      toast('反馈提交失败', 'error');
    }
  };

  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-accent/70 transition-colors hover:bg-accent/5 hover:text-accent"
      >
        <Lightbulb size={10} />
        参考了 {refs.length} 条经验
        <ChevronDown size={10} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="mt-1 space-y-1 rounded-md border border-border/50 bg-bg-card p-2">
          {refs.map((ref) => (
            <div key={ref.id} className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <span className="text-[10px] text-text-secondary">{ref.title}</span>
                <span className={`ml-1.5 rounded px-1 py-0.5 text-[8px] font-medium ${
                  ref.scope === 'personal' ? 'bg-purple-500/15 text-purple-500' : 'bg-sky-500/15 text-sky-400'
                }`}>
                  {ref.scope === 'personal' ? '个人' : '项目'}
                </span>
              </div>
              {feedbackGiven[ref.id] ? (
                <span className="text-[9px] text-text-muted">
                  {feedbackGiven[ref.id] === 'up' ? '已标记有效' : '已标记无效'}
                </span>
              ) : (
                <div className="flex gap-1">
                  <button
                    onClick={() => handleFeedback(ref.id, true)}
                    className="rounded p-0.5 text-text-muted hover:bg-status-done/10 hover:text-status-done"
                    title="有效"
                  >
                    <ThumbsUp size={10} />
                  </button>
                  <button
                    onClick={() => handleFeedback(ref.id, false)}
                    className="rounded p-0.5 text-text-muted hover:bg-status-error/10 hover:text-status-error"
                    title="无效"
                  >
                    <ThumbsDown size={10} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
