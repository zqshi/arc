import { useState, useEffect, useRef } from 'react';
import { Save, Settings } from 'lucide-react';
import { GitHubSection } from './GitHubSection';
import { ExecutionModeSection } from './ExecutionModeSection';
import { PhaseCapabilitiesSection } from './PhaseCapabilitiesSection';
import { ScanSection } from './ScanSection';
import { GitSyncSection } from './GitSyncSection';
import { Field } from './FormFields';
import { LocalPathField, InsightsPanel, ConventionsField } from './settings-tab-parts';
import { api, ApiError } from '../../api/client';
import FolderPicker from '../FolderPicker';
import { useToast } from '../Toast';
import type { ProcessConstraint, PhaseCapabilities } from '../../types/api';

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
          <LocalPathField
            localPath={form.local_path}
            isTemporaryWorkspace={isTemporaryWorkspace}
            migrating={migrating}
            onPick={() => setShowFolderPicker(true)}
          />

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
          processConstraint={form.process_constraint || 'free'}
          pipelineConfig={form.pipeline_config}
          conversationConfig={form.conversation_config}
          impact={impact}
          impactLoaded={impactLoaded}
          onChange={(constraint, pc, cc) => {
            setForm({ ...form, process_constraint: constraint, pipeline_config: pc, conversation_config: cc });
          }}
        />

        <GitSyncSection
          gitSync={gitSync}
          onChange={(gs) => setForm({
            ...form,
            conversation_config: { ...form.conversation_config, git_sync: gs },
          })}
        />

        <ConventionsField
          value={form.conventions}
          onChange={(v) => setForm({ ...form, conventions: v })}
        />

        <PhaseCapabilitiesSection
          projectId={projectId}
          phaseCapabilities={(form.pipeline_config?.phase_capabilities as PhaseCapabilities) ?? {}}
          onRefresh={onRefresh}
        />

        <InsightsPanel insights={insights} onAppendConvention={onAppendConvention} />
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
