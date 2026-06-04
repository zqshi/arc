import { useState, useEffect, useRef } from 'react';
import { Save, Lightbulb, Settings, FolderOpen } from 'lucide-react';
import { GitHubSection } from './GitHubSection';
import { ExecutionModeSection } from './ExecutionModeSection';
import { ScanSection } from './ScanSection';
import { GitSyncSection } from './GitSyncSection';
import { Field } from './FormFields';
import { api, ApiError } from '../../api/client';
import FolderPicker from '../FolderPicker';
import { useToast } from '../Toast';
import type { ExecutionMode, ProcessConstraint } from '../../types/api';

interface SettingsTabProps {
  projectId: string;
  form: {
    name: string;
    description: string;
    tech_stack: string;
    repo_url: string;
    local_path: string;
    conventions: string;
    codebase_summary: string;
    execution_mode: ExecutionMode;
    process_constraint: ProcessConstraint;
    pipeline_config: Record<string, unknown>;
    conversation_config: Record<string, unknown>;
  };
  setForm: (f: SettingsTabProps['form']) => void;
  dirty: boolean;
  onSave: () => void;
  onRefresh: () => void;
  insights: Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }>;
  onAppendConvention: (solution: string) => void;
  githubConnected?: boolean;
  githubRepo?: string | null;
  scanStatus?: 'idle' | 'scanning' | 'completed' | 'error';
  scanProgressText?: string;
  scanErrorText?: string;
}

export function SettingsTab({ projectId, form, setForm, dirty, onSave, onRefresh, insights, onAppendConvention, githubConnected, githubRepo, scanStatus: initialScanStatus, scanProgressText, scanErrorText }: SettingsTabProps) {
  const { toast } = useToast();

  const [ghToken, setGhToken] = useState('');
  const [ghConnecting, setGhConnecting] = useState(false);
  const [ghSyncing, setGhSyncing] = useState(false);
  const [ghWebhookUrl, setGhWebhookUrl] = useState('');
  const [ghIsConnected, setGhIsConnected] = useState(githubConnected ?? false);
  const [ghRepoName, setGhRepoName] = useState(githubRepo ?? null);

  useEffect(() => {
    setGhIsConnected(githubConnected ?? false);
    setGhRepoName(githubRepo ?? null);
  }, [githubConnected, githubRepo]);

  useEffect(() => {
    setGhToken('');
    setGhConnecting(false);
    setGhSyncing(false);
    setGhWebhookUrl('');
    setGhIsConnected(githubConnected ?? false);
    setGhRepoName(githubRepo ?? null);
    setGhCloneStep('idle');
    setGhClonePath('');
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const [ghCloneStep, setGhCloneStep] = useState<'idle' | 'prompt' | 'cloning' | 'done' | 'dismissed'>('idle');
  const [ghClonePath, setGhClonePath] = useState('');

  const handleGhConnect = async () => {
    if (!ghToken.trim() || !form.repo_url?.trim()) return;
    setGhConnecting(true);
    try {
      const result = await api.connectGitHub(projectId, ghToken.trim(), form.repo_url.trim());
      setGhIsConnected(true);
      setGhRepoName(result.repo);
      setGhWebhookUrl(result.webhook_url);
      setGhToken('');
      toast('GitHub 已连接', 'success');
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
      setForm({ ...form, local_path: result.local_path });
      setGhCloneStep('done');
      toast(`代码已${result.status === 'cloned' ? '克隆' : '更新'}到本地`, 'success');
      if (result.scan_started) {
        toast('正在扫描代码库...', 'success');
      }
      onRefresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Clone 失败';
      toast(msg, 'error');
      setGhCloneStep('prompt');
    }
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

  const [impact, setImpact] = useState<{ active_count: number; pending_count: number } | null>(null);
  const [impactLoaded, setImpactLoaded] = useState(false);
  const [showFolderPicker, setShowFolderPicker] = useState(false);
  const [migrating, setMigrating] = useState(false);

  const isTemporaryWorkspace = form.local_path?.includes('/.arc/workspaces/');

  const handleMigrateWorkspace = async (targetPath: string) => {
    setMigrating(true);
    try {
      const updated = await api.migrateWorkspace(projectId, targetPath);
      setForm({ ...form, local_path: updated.local_path });
      toast('工作区迁移完成', 'success');
      onRefresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : '迁移失败', 'error');
    } finally {
      setMigrating(false);
    }
  };

  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  useEffect(() => {
    onRefreshRef.current();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!projectId) return;
    api.getModeSwitchImpact(projectId).then((data) => {
      setImpact(data);
      setImpactLoaded(true);
    }).catch(() => setImpactLoaded(true));
  }, [projectId]);

  const gitSync = (form.conversation_config?.git_sync || {}) as Record<string, unknown>;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <Settings size={13} /> 项目设置
        </h2>
        <button
          onClick={onSave}
          disabled={!dirty}
          className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-[11px] font-medium text-white transition-opacity hover:bg-accent-hover disabled:opacity-30"
        >
          <Save size={12} /> 保存更改
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-bg-card p-4 space-y-4">
          <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide">基本信息</p>
          <Field label="项目名称" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
          <Field label="描述" value={form.description} onChange={(v) => setForm({ ...form, description: v })} multiline />
        </div>

        <div className="rounded-lg border border-border bg-bg-card p-4 space-y-4">
          <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide">技术配置</p>
          <Field label="技术栈" value={form.tech_stack} onChange={(v) => setForm({ ...form, tech_stack: v })} placeholder="例如：React + FastAPI + PostgreSQL" />
          <div>
            <label className="mb-1 block text-[11px] font-medium text-text-tertiary">本地工作目录</label>
            <button
              type="button"
              onClick={() => setShowFolderPicker(true)}
              className="flex h-9 w-full items-center gap-2 rounded-md border border-border bg-bg-input px-3 text-left text-sm transition-colors hover:border-border-active"
            >
              <FolderOpen size={14} className="flex-shrink-0 text-text-muted" />
              {form.local_path ? (
                <span className="flex-1 truncate font-mono text-xs text-text-primary">{form.local_path}</span>
              ) : (
                <span className="flex-1 truncate text-text-muted">点击选择目录...</span>
              )}
            </button>
            <p className="mt-1 text-[10px] text-text-muted">Coding Agent 将在此目录下读写代码</p>
            {isTemporaryWorkspace && (
              <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                <p className="text-[11px] font-medium text-amber-400">⚡ 临时工作区</p>
                <p className="mt-0.5 text-[10px] text-text-muted">
                  当前使用自动创建的临时目录。建议关联正式项目目录以便版本管理。
                </p>
                <button
                  type="button"
                  disabled={migrating}
                  onClick={() => setShowFolderPicker(true)}
                  className="mt-1.5 rounded bg-amber-500/20 px-2 py-1 text-[10px] font-medium text-amber-300 hover:bg-amber-500/30 disabled:opacity-50"
                >
                  {migrating ? '迁移中...' : '选择目录并迁移'}
                </button>
              </div>
            )}
          </div>

          <ScanSection
            projectId={projectId}
            localPath={form.local_path}
            codebaseSummary={form.codebase_summary}
            dirty={dirty}
            initialScanStatus={initialScanStatus}
            scanProgressText={scanProgressText}
            scanErrorText={scanErrorText}
            onRefresh={onRefresh}
            onSummaryChange={(summary) => setForm({ ...form, codebase_summary: summary })}
          />
        </div>

        <GitHubSection
          isConnected={ghIsConnected}
          repoName={ghRepoName}
          repoUrl={form.repo_url || ''}
          localPath={form.local_path || ''}
          webhookUrl={ghWebhookUrl}
          cloneStep={ghCloneStep}
          clonePath={ghClonePath}
          token={ghToken}
          connecting={ghConnecting}
          syncing={ghSyncing}
          onTokenChange={setGhToken}
          onClonePathChange={setGhClonePath}
          onConnect={handleGhConnect}
          onDisconnect={handleGhDisconnect}
          onSync={handleGhSync}
          onClone={handleGhClone}
          onSkipClone={() => setGhCloneStep('dismissed')}
          onPickFolder={() => setShowFolderPicker(true)}
          onRepoUrlChange={(v) => setForm({ ...form, repo_url: v })}
        />

        <ExecutionModeSection
          executionMode={form.execution_mode}
          processConstraint={form.process_constraint || 'free'}
          pipelineConfig={form.pipeline_config}
          conversationConfig={form.conversation_config}
          impact={impact}
          impactLoaded={impactLoaded}
          onChange={(constraint, pc, cc) => {
            const execMode = constraint === 'strict' ? 'pipeline' : 'conversation';
            setForm({ ...form, process_constraint: constraint, execution_mode: execMode, pipeline_config: pc, conversation_config: cc });
          }}
        />

        <GitSyncSection
          gitSync={gitSync}
          onChange={(gs) => setForm({
            ...form,
            conversation_config: { ...form.conversation_config, git_sync: gs },
          })}
        />

        <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
          <p className="mb-3 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">项目规范</p>
          <Field label="规范内容" value={form.conventions} onChange={(v) => setForm({ ...form, conventions: v })} multiline placeholder="AI在生成方案和代码时会遵守这些规范" />
        </div>

        {insights.length > 0 && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 lg:col-span-2">
            <p className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-amber-600">
              <Lightbulb size={13} /> 规范建议
            </p>
            <p className="mb-3 text-[11px] text-text-muted">以下经验已多次验证有效，建议纳入项目规范</p>
            <div className="space-y-2">
              {insights.map((ins) => (
                <div key={ins.id} className="flex items-start gap-3 rounded-md border border-amber-500/15 bg-bg-card p-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-text-primary">{ins.title}</p>
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-text-secondary">{ins.solution}</p>
                    <div className="mt-1 flex gap-2 text-[10px] text-text-muted">
                      <span>信心 {Math.round(ins.confidence * 100)}%</span>
                      <span>复用 {ins.reuse_count} 次</span>
                    </div>
                  </div>
                  <button
                    onClick={() => onAppendConvention(ins.solution)}
                    className="flex-shrink-0 rounded-md border border-amber-500/30 px-2 py-1 text-[10px] font-medium text-amber-600 hover:bg-amber-500/10"
                  >
                    纳入规范
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <FolderPicker
        open={showFolderPicker}
        onClose={() => setShowFolderPicker(false)}
        onSelect={(path) => {
          if (isTemporaryWorkspace) {
            handleMigrateWorkspace(path);
          } else {
            setForm({ ...form, local_path: path });
          }
        }}
        initialPath={form.local_path || '~'}
      />
    </section>
  );
}
