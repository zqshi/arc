import { Pencil, Check, Archive, ArrowUpRight, Beaker } from 'lucide-react';
import type { Experience } from '../types/api';

export interface ExperienceDetailActions {
  onClose: () => void;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  onConfirm: () => void;
  onArchive: () => void;
  onPromote: () => void;
  onDistill: () => void;
}

interface FooterProps {
  experience: Experience;
  editing: boolean;
  distilling: boolean;
  actions: ExperienceDetailActions;
}

export function ExperienceDetailFooter({ experience, editing, distilling, actions }: FooterProps) {
  return (
    <div className="flex items-center justify-between border-t border-border px-5 py-3">
      <span className="text-[10px] text-text-muted">
        创建于 {new Date(experience.created_at).toLocaleDateString('zh-CN')}
      </span>
      <div className="flex items-center gap-2">
        {editing ? (
          <>
            <button
              onClick={actions.onCancel}
              className="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary"
            >
              取消
            </button>
            <button
              onClick={actions.onSave}
              className="rounded-md bg-accent px-3 py-1.5 text-xs text-white hover:bg-accent-hover"
            >
              保存
            </button>
          </>
        ) : (
          <>
            {experience.status !== 'archived' && (
              <button
                onClick={actions.onEdit}
                className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary hover:text-text-primary"
              >
                <Pencil size={11} /> 编辑
              </button>
            )}
            {experience.status === 'draft' && (
              <button
                onClick={actions.onConfirm}
                className="flex items-center gap-1 rounded-md border border-status-done/30 px-2.5 py-1.5 text-xs text-status-done hover:bg-status-done/10"
              >
                <Check size={11} /> 确认
              </button>
            )}
            {experience.status !== 'archived' && (
              <button
                onClick={actions.onArchive}
                className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-muted hover:text-text-secondary"
              >
                <Archive size={11} /> 归档
              </button>
            )}
            {experience.scope === 'project' && experience.status === 'confirmed' && (
              <>
                <button
                  onClick={actions.onDistill}
                  disabled={distilling}
                  className="flex items-center gap-1 rounded-md border border-accent/30 px-2.5 py-1.5 text-xs text-accent hover:bg-accent/10 disabled:opacity-50"
                >
                  <Beaker size={11} /> {distilling ? '提炼中...' : '提炼'}
                </button>
                <button
                  onClick={actions.onPromote}
                  className="flex items-center gap-1 rounded-md border border-purple-500/30 px-2.5 py-1.5 text-xs text-purple-500 hover:bg-purple-500/10"
                >
                  <ArrowUpRight size={11} /> 升级为个人
                </button>
              </>
            )}
            <button
              onClick={actions.onClose}
              className="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary"
            >
              关闭
            </button>
          </>
        )}
      </div>
    </div>
  );
}
