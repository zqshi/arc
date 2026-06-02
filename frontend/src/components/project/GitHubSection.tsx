/**
 * GitHub 集成设置面板 — 从 SettingsTab 提取。
 * 职责：连接/断开 GitHub、克隆仓库、同步 Issues、Webhook 配置。
 */

import { FolderOpen, Link2, Unlink, RotateCw, RefreshCw } from 'lucide-react';

function GithubIcon({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

interface GitHubSectionProps {
  isConnected: boolean;
  repoName: string | null;
  repoUrl: string;
  localPath: string;
  webhookUrl: string;
  cloneStep: string;
  clonePath: string;
  token: string;
  connecting: boolean;
  syncing: boolean;
  onTokenChange: (v: string) => void;
  onClonePathChange: (v: string) => void;
  onConnect: () => void;
  onDisconnect: () => void;
  onSync: () => void;
  onClone: () => void;
  onSkipClone: () => void;
  onPickFolder: () => void;
  onRepoUrlChange: (v: string) => void;
}

export function GitHubSection({
  isConnected, repoName, repoUrl, localPath, webhookUrl, cloneStep, clonePath,
  token, connecting, syncing,
  onTokenChange, onClonePathChange, onConnect, onDisconnect, onSync, onClone, onSkipClone, onPickFolder, onRepoUrlChange,
}: GitHubSectionProps) {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
      <p className="mb-3 flex items-center gap-2 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">
        <GithubIcon size={13} /> GitHub 集成
      </p>
      {isConnected ? (
        <ConnectedView
          repoName={repoName}
          localPath={localPath}
          webhookUrl={webhookUrl}
          cloneStep={cloneStep}
          clonePath={clonePath}
          syncing={syncing}
          onClonePathChange={onClonePathChange}
          onDisconnect={onDisconnect}
          onSync={onSync}
          onClone={onClone}
          onSkipClone={onSkipClone}
          onPickFolder={onPickFolder}
        />
      ) : (
        <DisconnectedView
          repoUrl={repoUrl}
          token={token}
          connecting={connecting}
          onTokenChange={onTokenChange}
          onRepoUrlChange={onRepoUrlChange}
          onConnect={onConnect}
        />
      )}
    </div>
  );
}

function ConnectedView({
  repoName, localPath, webhookUrl, cloneStep, clonePath, syncing,
  onClonePathChange, onDisconnect, onSync, onClone, onSkipClone, onPickFolder,
}: Omit<GitHubSectionProps, 'isConnected' | 'repoUrl' | 'token' | 'connecting' | 'onTokenChange' | 'onConnect' | 'onRepoUrlChange'>) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between rounded-md bg-status-done/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <Link2 size={13} className="text-status-done" />
          <span className="text-xs font-medium text-status-done">已连接</span>
          {repoName && <span className="text-xs text-text-secondary">{repoName}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onSync} disabled={syncing} className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-text-secondary hover:bg-bg-elevated disabled:opacity-40">
            <RotateCw size={10} className={syncing ? 'animate-spin' : ''} />
            {syncing ? '同步中...' : '同步 Issues'}
          </button>
          <button onClick={onDisconnect} className="flex items-center gap-1 rounded-md border border-status-error/30 px-2 py-1 text-[10px] font-medium text-status-error hover:bg-status-error/10">
            <Unlink size={10} /> 断开
          </button>
        </div>
      </div>

      {!localPath && cloneStep !== 'dismissed' && cloneStep !== 'cloning' && cloneStep !== 'done' && (
        <div className="rounded-md border border-accent/30 bg-accent/5 p-3 space-y-2">
          <p className="text-[11px] font-medium text-text-primary">📂 关联本地代码</p>
          <p className="text-[10px] text-text-muted">克隆仓库到本地后，AI 助手可以直接读取和修改代码。</p>
          <div className="flex items-center gap-2">
            <input type="text" value={clonePath} onChange={(e) => onClonePathChange(e.target.value)}
              placeholder={`默认: ~/.arc/repos/${repoName || 'owner/repo'}`}
              className="h-7 flex-1 rounded-md border border-border bg-bg-input px-2 text-[11px] text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none" />
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClone} className="flex h-7 items-center gap-1 rounded-md bg-accent px-3 text-[10px] font-medium text-white hover:bg-accent-hover">
              <FolderOpen size={11} /> 克隆到本地
            </button>
            <button onClick={onPickFolder} className="flex h-7 items-center gap-1 rounded-md border border-border px-3 text-[10px] font-medium text-text-secondary hover:bg-bg-elevated">
              选择已有目录
            </button>
            <button onClick={onSkipClone} className="flex h-7 items-center gap-1 rounded-md px-2 text-[10px] text-text-muted hover:text-text-secondary">
              跳过
            </button>
          </div>
        </div>
      )}

      {cloneStep === 'cloning' && (
        <div className="flex items-center gap-2 rounded-md border border-border/50 bg-bg-elevated px-3 py-2">
          <RefreshCw size={12} className="animate-spin text-accent" />
          <span className="text-[11px] text-text-secondary">正在克隆仓库...</span>
        </div>
      )}

      {cloneStep === 'done' && (
        <div className="flex items-center gap-2 rounded-md border border-status-done/30 bg-status-done/5 px-3 py-2">
          <FolderOpen size={12} className="text-status-done" />
          <span className="text-[11px] text-text-secondary">已关联: <code className="text-[10px]">{localPath}</code></span>
        </div>
      )}

      {webhookUrl && (
        <div className="rounded-md border border-border/50 px-3 py-2">
          <p className="text-[10px] text-text-muted">Webhook URL (在 GitHub 仓库 Settings → Webhooks 中配置)</p>
          <code className="mt-1 block break-all rounded bg-bg-elevated px-2 py-1 text-[11px] text-text-secondary">
            {window.location.origin}{webhookUrl}
          </code>
        </div>
      )}
    </div>
  );
}

function DisconnectedView({
  repoUrl, token, connecting, onTokenChange, onRepoUrlChange, onConnect,
}: Pick<GitHubSectionProps, 'repoUrl' | 'token' | 'connecting' | 'onTokenChange' | 'onRepoUrlChange' | 'onConnect'>) {
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-text-muted">连接 GitHub 后，Issues 会自动同步为项目需求，完成后自动回写。</p>
      <div>
        <label className="mb-1 block text-[11px] font-medium text-text-tertiary">代码仓库地址</label>
        <input type="text" value={repoUrl} onChange={(e) => onRepoUrlChange(e.target.value)}
          placeholder="https://github.com/owner/repo"
          className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none" />
      </div>
      <div>
        <label className="mb-1 block text-[11px] font-medium text-text-tertiary">Personal Access Token</label>
        <p className="mb-2 text-[10px] text-text-muted">
          需要 <code className="rounded bg-bg-elevated px-1">repo</code> 权限。
          <a href="https://github.com/settings/tokens/new?scopes=repo&description=Arc+Workstation" target="_blank" rel="noopener noreferrer" className="ml-1 text-accent hover:underline">
            去 GitHub 创建 →
          </a>
        </p>
        <div className="flex items-center gap-2">
          <input type="text" value={token} onChange={(e) => onTokenChange(e.target.value)}
            placeholder="ghp_xxxxxxxxxxxx" autoComplete="off" data-1p-ignore data-lpignore="true"
            className="h-8 flex-1 rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
            onKeyDown={(e) => { if (e.key === 'Enter') onConnect(); }} />
          <button onClick={onConnect} disabled={!token.trim() || connecting || !repoUrl?.trim()}
            className="flex h-8 items-center gap-1 rounded-md bg-accent px-3 text-[11px] font-medium text-white hover:bg-accent-hover disabled:opacity-40">
            <Link2 size={11} /> {connecting ? '连接中...' : '连接'}
          </button>
        </div>
      </div>
    </div>
  );
}
