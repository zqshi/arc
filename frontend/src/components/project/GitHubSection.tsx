import { useState, useEffect } from 'react';
import { FolderOpen, RefreshCw, RotateCw, Link2, Unlink } from 'lucide-react';
import { api, ApiError } from '../../api/client';
import { useToast } from '../Toast';
import { Field } from './FormFields';

function GithubIcon({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

interface GitHubSectionProps {
  projectId: string;
  repoUrl: string;
  localPath: string;
  onRepoUrlChange: (v: string) => void;
  onLocalPathChange: (v: string) => void;
  onOpenFolderPicker: () => void;
  onRefresh: () => void;
  onScanStarted: () => void;
  githubConnected?: boolean;
  githubRepo?: string | null;
}

export function GitHubSection({
  projectId,
  repoUrl,
  localPath,
  onRepoUrlChange,
  onLocalPathChange,
  onOpenFolderPicker,
  onRefresh,
  onScanStarted,
  githubConnected,
  githubRepo,
}: GitHubSectionProps) {
  const { toast } = useToast();

  const [ghToken, setGhToken] = useState('');
  const [ghConnecting, setGhConnecting] = useState(false);
  const [ghSyncing, setGhSyncing] = useState(false);
  const [ghWebhookUrl, setGhWebhookUrl] = useState('');
  const [ghIsConnected, setGhIsConnected] = useState(githubConnected ?? false);
  const [ghRepoName, setGhRepoName] = useState(githubRepo ?? null);
  const [ghCloneStep, setGhCloneStep] = useState<'idle' | 'prompt' | 'cloning' | 'done' | 'dismissed'>('idle');
  const [ghClonePath, setGhClonePath] = useState('');

  useEffect(() => {
    setGhIsConnected(githubConnected ?? false);
    setGhRepoName(githubRepo ?? null);
  }, [githubConnected, githubRepo]);

  // Reset all local GitHub state when switching projects
  useEffect(() => {
    setGhToken('');
    setGhConnecting(false);
    setGhSyncing(false);
    setGhWebhookUrl('');
    setGhIsConnected(githubConnected ?? false);
    setGhRepoName(githubRepo ?? null);
    setGhCloneStep('idle');
    setGhClonePath('');
  }, [projectId]);

  const handleGhConnect = async () => {
    if (!ghToken.trim() || !repoUrl?.trim()) return;
    setGhConnecting(true);
    try {
      const result = await api.connectGitHub(projectId, ghToken.trim(), repoUrl.trim());
      setGhIsConnected(true);
      setGhRepoName(result.repo);
      setGhWebhookUrl(result.webhook_url);
      setGhToken('');
      toast('GitHub 已连接', 'success');

      const cr = result.clone_result;
      if (cr && cr.status !== 'failed' && cr.local_path) {
        onLocalPathChange(cr.local_path);
        setGhCloneStep('done');
        toast(`代码已${cr.status === 'cloned' ? '克隆' : '更新'}到本地`, 'success');
        if (cr.scan_started) {
          onScanStarted();
        }
      } else if (cr && cr.status === 'failed') {
        setGhCloneStep('prompt');
      }
      onRefresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'GitHub 连接失败';
      toast(msg, 'error');
    } finally {
      setGhConnecting(false);
    }
  };

  const handleGhDisconnect = async () => {
    try {
      await api.disconnectGitHub(projectId);
      setGhIsConnected(false);
      setGhRepoName(null);
      setGhWebhookUrl('');
      setGhCloneStep('idle');
      toast('GitHub 已断开', 'success');
      onRefresh();
    } catch {
      toast('断开失败', 'error');
    }
  };

  const handleGhClone = async () => {
    setGhCloneStep('cloning');
    try {
      const result = await api.cloneGitHubRepo(projectId, ghClonePath || undefined);
      onLocalPathChange(result.local_path);
      setGhCloneStep('done');
      toast(`代码已${result.status === 'cloned' ? '克隆' : '更新'}到本地`, 'success');
      if (result.scan_started) {
        onScanStarted();
      }
      onRefresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Clone 失败';
      toast(msg, 'error');
      setGhCloneStep('prompt');
    }
  };

  const handleGhSkipClone = () => {
    setGhCloneStep('dismissed');
  };

  const handleGhSync = async () => {
    setGhSyncing(true);
    try {
      const result = await api.syncGitHubIssues(projectId);
      toast(`同步完成: ${result.created} 新建, ${result.updated} 更新`, 'success');
      onRefresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '同步失败';
      toast(msg, 'error');
    } finally {
      setGhSyncing(false);
    }
  };

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
      <p className="mb-3 flex items-center gap-2 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">
        <GithubIcon size={13} /> GitHub 集成
      </p>
      {ghIsConnected ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-md bg-status-done/10 px-3 py-2">
            <div className="flex items-center gap-2">
              <Link2 size={13} className="text-status-done" />
              <span className="text-xs font-medium text-status-done">已连接</span>
              {ghRepoName && (
                <span className="text-xs text-text-secondary">{ghRepoName}</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleGhSync}
                disabled={ghSyncing}
                className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-text-secondary hover:bg-bg-elevated disabled:opacity-40"
              >
                <RotateCw size={10} className={ghSyncing ? 'animate-spin' : ''} />
                {ghSyncing ? '同步中...' : '同步 Issues'}
              </button>
              <button
                onClick={handleGhDisconnect}
                className="flex items-center gap-1 rounded-md border border-status-error/30 px-2 py-1 text-[10px] font-medium text-status-error hover:bg-status-error/10"
              >
                <Unlink size={10} /> 断开
              </button>
            </div>
          </div>

          {/* Clone prompt */}
          {!localPath && ghCloneStep !== 'dismissed' && ghCloneStep !== 'cloning' && ghCloneStep !== 'done' && (
            <div className="rounded-md border border-accent/30 bg-accent/5 p-3 space-y-2">
              <p className="text-[11px] font-medium text-text-primary">📂 关联本地代码</p>
              <p className="text-[10px] text-text-muted">
                克隆仓库到本地后，AI 助手可以直接读取和修改代码。不关联则只能同步 Issues。
              </p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={ghClonePath}
                  onChange={(e) => setGhClonePath(e.target.value)}
                  placeholder={`默认: ~/.arc/repos/${ghRepoName || 'owner/repo'}`}
                  className="h-7 flex-1 rounded-md border border-border bg-bg-input px-2 text-[11px] text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleGhClone}
                  className="flex h-7 items-center gap-1 rounded-md bg-accent px-3 text-[10px] font-medium text-white hover:bg-accent-hover"
                >
                  <FolderOpen size={11} /> 克隆到本地
                </button>
                <button
                  onClick={onOpenFolderPicker}
                  className="flex h-7 items-center gap-1 rounded-md border border-border px-3 text-[10px] font-medium text-text-secondary hover:bg-bg-elevated"
                >
                  选择已有目录
                </button>
                <button
                  onClick={handleGhSkipClone}
                  className="flex h-7 items-center gap-1 rounded-md px-2 text-[10px] text-text-muted hover:text-text-secondary"
                >
                  跳过
                </button>
              </div>
            </div>
          )}

          {ghCloneStep === 'cloning' && (
            <div className="flex items-center gap-2 rounded-md border border-border/50 bg-bg-elevated px-3 py-2">
              <RefreshCw size={12} className="animate-spin text-accent" />
              <span className="text-[11px] text-text-secondary">正在克隆仓库...</span>
            </div>
          )}

          {ghCloneStep === 'done' && (
            <div className="flex items-center gap-2 rounded-md border border-status-done/30 bg-status-done/5 px-3 py-2">
              <FolderOpen size={12} className="text-status-done" />
              <span className="text-[11px] text-text-secondary">
                已关联: <code className="text-[10px]">{localPath}</code>
              </span>
            </div>
          )}

          {ghWebhookUrl && (
            <div className="rounded-md border border-border/50 px-3 py-2">
              <p className="text-[10px] text-text-muted">
                Webhook URL (在 GitHub 仓库 Settings → Webhooks 中配置)
              </p>
              <code className="mt-1 block break-all rounded bg-bg-elevated px-2 py-1 text-[11px] text-text-secondary">
                {window.location.origin}{ghWebhookUrl}
              </code>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-[11px] text-text-muted">
            连接 GitHub 后，Issues 会自动同步为 Arc 需求，完成后自动回写。
          </p>
          <Field
            label="代码仓库地址"
            value={repoUrl}
            onChange={onRepoUrlChange}
            placeholder="https://github.com/owner/repo"
          />
          <div>
            <label className="mb-1 block text-[11px] font-medium text-text-tertiary">Personal Access Token</label>
            <p className="mb-2 text-[10px] text-text-muted">
              需要 <code className="rounded bg-bg-elevated px-1">repo</code> 权限。
              <a
                href="https://github.com/settings/tokens/new?scopes=repo&description=Arc+Workstation"
                target="_blank"
                rel="noopener noreferrer"
                className="ml-1 text-accent hover:underline"
              >
                去 GitHub 创建 →
              </a>
            </p>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={ghToken}
                onChange={(e) => setGhToken(e.target.value)}
                placeholder="ghp_xxxxxxxxxxxx"
                autoComplete="off"
                data-1p-ignore
                data-lpignore="true"
                className="h-8 flex-1 rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleGhConnect();
                }}
              />
              <button
                onClick={handleGhConnect}
                disabled={!ghToken.trim() || ghConnecting || !repoUrl?.trim()}
                className="flex h-8 items-center gap-1 rounded-md bg-accent px-3 text-[11px] font-medium text-white hover:bg-accent-hover disabled:opacity-40"
              >
                <Link2 size={11} />
                {ghConnecting ? '连接中...' : '连接'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
