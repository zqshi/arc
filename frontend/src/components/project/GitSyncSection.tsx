interface GitSyncConfig {
  auto_commit?: boolean;
  auto_push?: boolean;
  commit_prefix?: string;
  target_branch?: string;
}

interface GitSyncSectionProps {
  gitSync: GitSyncConfig;
  onChange: (gitSync: GitSyncConfig) => void;
}

export function GitSyncSection({ gitSync, onChange }: GitSyncSectionProps) {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
      <p className="mb-3 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">Git 同步</p>
      <p className="mb-3 text-[11px] text-text-muted">开发完成后自动将代码变更提交到关联的 Git 仓库。</p>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-text-primary">自动提交</p>
            <p className="text-[11px] text-text-muted">Agent 完成开发后自动 git commit</p>
          </div>
          <button
            onClick={() => onChange({ ...gitSync, auto_commit: !gitSync.auto_commit })}
            className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
              gitSync.auto_commit ? 'bg-accent' : 'bg-border'
            }`}
          >
            <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
              gitSync.auto_commit ? 'translate-x-5' : ''
            }`} />
          </button>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-text-primary">自动推送</p>
            <p className="text-[11px] text-text-muted">提交后自动 git push 到远端</p>
          </div>
          <button
            onClick={() => onChange({ ...gitSync, auto_push: !gitSync.auto_push })}
            className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
              gitSync.auto_push ? 'bg-accent' : 'bg-border'
            }`}
          >
            <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
              gitSync.auto_push ? 'translate-x-5' : ''
            }`} />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-[11px] text-text-muted whitespace-nowrap">Commit 前缀</label>
          <input
            type="text"
            value={gitSync.commit_prefix || 'feat'}
            onChange={(e) => onChange({ ...gitSync, commit_prefix: e.target.value })}
            placeholder="feat"
            className="h-7 w-24 rounded-md border border-border bg-bg-input px-2 text-xs text-text-primary focus:border-border-active focus:outline-none"
          />
          <label className="text-[11px] text-text-muted whitespace-nowrap">目标分支</label>
          <input
            type="text"
            value={gitSync.target_branch || ''}
            onChange={(e) => onChange({ ...gitSync, target_branch: e.target.value })}
            placeholder="留空使用当前分支"
            className="h-7 flex-1 rounded-md border border-border bg-bg-input px-2 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
          />
        </div>
      </div>
    </div>
  );
}
