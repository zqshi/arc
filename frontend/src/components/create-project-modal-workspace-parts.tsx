import type { ReactNode } from 'react';
import { FolderOpen, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import FolderPicker from './FolderPicker';
import type { WorkspaceType } from '../types/api';
import { WORKSPACE_OPTIONS } from './create-project-modal-parts';

/** Step2: 工作区选择 */
export function WorkspaceStep({
  workspaceType,
  localPath,
  showPicker,
  repoUrl,
  githubToken,
  onWorkspaceTypeChange,
  onShowPickerChange,
  onLocalPathChange,
  onRepoUrlChange,
  onGithubTokenChange,
}: {
  workspaceType: WorkspaceType;
  localPath: string;
  showPicker: boolean;
  repoUrl: string;
  githubToken: string;
  onWorkspaceTypeChange: (t: WorkspaceType, showPicker: boolean) => void;
  onShowPickerChange: (v: boolean) => void;
  onLocalPathChange: (v: string) => void;
  onRepoUrlChange: (v: string) => void;
  onGithubTokenChange: (v: string) => void;
}) {
  return (
    <>
      <div className="space-y-2">
        {WORKSPACE_OPTIONS.map((opt) => {
          const Icon = opt.icon;
          const active = workspaceType === opt.type;
          return (
            <button
              key={opt.type}
              onClick={() => {
                onWorkspaceTypeChange(opt.type, opt.type === 'local');
              }}
              className={`flex w-full items-start gap-3 rounded-lg border px-4 py-3 text-left transition-colors ${
                active
                  ? 'border-accent bg-accent/5'
                  : 'border-border hover:border-border-active hover:bg-bg-elevated/50'
              }`}
            >
              <Icon size={16} className={`mt-0.5 flex-shrink-0 ${active ? 'text-accent' : 'text-text-muted'}`} />
              <div className="min-w-0">
                <div className={`text-xs font-medium ${active ? 'text-accent' : 'text-text-primary'}`}>
                  {opt.title}
                </div>
                <div className="text-[11px] text-text-muted">{opt.desc}</div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Workspace-specific inputs */}
      {workspaceType === 'local' && (
        <div className="mt-3">
          {showPicker ? (
            <div className="overflow-hidden rounded-lg border border-border">
              <FolderPicker
                open={showPicker}
                onSelect={(path) => {
                  onLocalPathChange(path);
                  onShowPickerChange(false);
                }}
                onClose={() => onShowPickerChange(false)}
              />
            </div>
          ) : localPath ? (
            <div className="flex items-center gap-2 rounded-md bg-bg-elevated px-3 py-2">
              <FolderOpen size={12} className="flex-shrink-0 text-accent" />
              <span className="truncate text-xs text-text-primary">{localPath}</span>
              <button
                onClick={() => onShowPickerChange(true)}
                className="ml-auto flex-shrink-0 text-[10px] text-accent hover:underline"
              >
                更换
              </button>
            </div>
          ) : null}
        </div>
      )}

      {workspaceType === 'github' && (
        <div className="mt-3 space-y-2">
          <input
            type="text"
            value={repoUrl}
            onChange={(e) => onRepoUrlChange(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
          />
          <input
            type="password"
            value={githubToken}
            onChange={(e) => onGithubTokenChange(e.target.value)}
            placeholder="Personal Access Token（可选，私有仓库必填）"
            className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
          />
        </div>
      )}
    </>
  );
}

/** 底部 Footer (上一步/取消/下一步/创建) */
export function ModalFooter({
  step,
  canNext,
  canCreate,
  creating,
  onBack,
  onClose,
  onNext,
  onCreate,
}: {
  step: 'info' | 'workspace';
  canNext: boolean;
  canCreate: boolean;
  creating: boolean;
  onBack: () => void;
  onClose: () => void;
  onNext: () => void;
  onCreate: () => void;
}): ReactNode {
  return (
    <div className="flex items-center justify-between border-t border-border px-5 py-3">
      <div>
        {step === 'workspace' && (
          <button
            onClick={onBack}
            className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary"
          >
            <ChevronLeft size={12} /> 上一步
          </button>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onClose}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary"
        >
          取消
        </button>
        {step === 'info' ? (
          <button
            onClick={onNext}
            disabled={!canNext}
            className="flex items-center gap-1 rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-40"
          >
            下一步 <ChevronRight size={12} />
          </button>
        ) : (
          <button
            onClick={onCreate}
            disabled={!canCreate || creating}
            className="flex items-center gap-1 rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-40"
          >
            {creating ? <Loader2 size={12} className="animate-spin" /> : null}
            创建项目
          </button>
        )}
      </div>
    </div>
  );
}
