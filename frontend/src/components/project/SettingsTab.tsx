import { useState, useEffect, useRef, useCallback } from 'react';
import { Save, Lightbulb, Settings, Workflow, MessageSquare, AlertTriangle, Zap, FolderOpen, ScanSearch, RefreshCw, AlertCircle, Link2, Unlink, RotateCw } from 'lucide-react';

function GithubIcon({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}
import { Field } from './FormFields';
import { api, ApiError } from '../../api/client';
import type { ScanEvent } from '../../api/client';
import FolderPicker from '../FolderPicker';
import { useToast } from '../Toast';
import type { ExecutionMode } from '../../types/api';
import { EXECUTION_MODE_LABELS, EXECUTION_MODE_DESCRIPTIONS } from '../../types/api';

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
  const isAutopilot = Boolean(form.pipeline_config?.auto_advance) || form.conversation_config?.agent_autonomy === 'full';
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

      // Backend auto-clones when local_path is empty
      const cr = result.clone_result;
      if (cr && cr.status !== 'failed' && cr.local_path) {
        setForm({ ...form, local_path: cr.local_path });
        setGhCloneStep('done');
        toast(`代码已${cr.status === 'cloned' ? '克隆' : '更新'}到本地`, 'success');
        if (cr.scan_started) {
          toast('正在扫描代码库...', 'success');
        }
      } else if (cr && cr.status === 'failed') {
        // Auto-clone failed — fall back to manual prompt
        setGhCloneStep('prompt');
      } else if (!form.local_path && !cr) {
        // No auto-clone attempted (local_path was already set)
        // do nothing
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

  const [impact, setImpact] = useState<{ active_count: number; pending_count: number } | null>(null);
  const [impactLoaded, setImpactLoaded] = useState(false);
  const [showFolderPicker, setShowFolderPicker] = useState(false);

  // Scan state — initialize from server-persisted status
  const [scanning, setScanning] = useState(initialScanStatus === 'scanning');
  const [scanStage, setScanStage] = useState(scanProgressText || '');
  const [scanContent, setScanContent] = useState('');
  const [scanError, setScanError] = useState(initialScanStatus === 'error' ? (scanErrorText || '扫描失败') : '');
  const abortRef = useRef<AbortController | null>(null);

  // Shared SSE subscription logic
  const subscribeToScanStream = useCallback(() => {
    setScanning(true);
    setScanError('');

    const controller = new AbortController();
    abortRef.current = controller;

    const timeout = setTimeout(() => {
      controller.abort();
      setScanError('扫描超时，请重试');
      setScanning(false);
    }, 5 * 60 * 1000);

    api.scanCodebaseStream(projectId, (event: ScanEvent) => {
      switch (event.event) {
        case 'replay':
          // Accumulated content from before this subscription — show history
          setScanContent(event.content || '');
          break;
        case 'stage':
          setScanStage(event.message || '');
          break;
        case 'chunk':
          setScanContent((prev) => prev + (event.content || ''));
          break;
        case 'done':
          clearTimeout(timeout);
          setScanContent(event.summary || '');
          setScanning(false);
          setScanStage('');
          onRefresh();
          break;
        case 'error':
          clearTimeout(timeout);
          setScanError(event.detail || '扫描失败');
          setScanning(false);
          setScanStage('');
          break;
        case 'close':
          clearTimeout(timeout);
          setScanning(false);
          break;
      }
    }, controller.signal);
  }, [projectId, onRefresh]);

  // Auto-recover SSE subscription when component mounts and scan is running on server
  useEffect(() => {
    if (initialScanStatus === 'scanning' && projectId) {
      subscribeToScanStream();
      return () => { abortRef.current?.abort(); };
    }
  }, [initialScanStatus, projectId, subscribeToScanStream]);

  const startScan = useCallback(async (force: boolean) => {
    setScanning(true);
    setScanStage('');
    setScanContent('');
    setScanError('');

    try {
      const result = await api.scanCodebase(projectId, force);
      if (result.cached && result.summary) {
        setForm({ ...form, codebase_summary: result.summary });
        setScanning(false);
        return;
      }

      // Task started — subscribe to SSE stream
      const controller = new AbortController();
      abortRef.current = controller;

      // Safety timeout: abort if SSE hangs for 5 minutes
      const timeout = setTimeout(() => {
        controller.abort();
        setScanError('扫描超时，请重试');
        setScanning(false);
      }, 5 * 60 * 1000);

      api.scanCodebaseStream(projectId, (event: ScanEvent) => {
        switch (event.event) {
          case 'stage':
            setScanStage(event.message || '');
            break;
          case 'chunk':
            setScanContent((prev) => prev + (event.content || ''));
            break;
          case 'done':
            clearTimeout(timeout);
            setScanContent(event.summary || '');
            setScanning(false);
            setScanStage('');
            onRefresh();
            break;
          case 'error':
            clearTimeout(timeout);
            setScanError(event.detail || '扫描失败');
            setScanning(false);
            setScanStage('');
            break;
          case 'close':
            clearTimeout(timeout);
            setScanning(false);
            break;
        }
      }, controller.signal);
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : '扫描启动失败';
      // 409 means scan is already running — subscribe to SSE instead of showing error
      if (errMsg.includes('409') || errMsg.includes('扫描进行中') || errMsg.includes('重复')) {
        setScanError('');
        subscribeToScanStream();
      } else {
        setScanError(errMsg);
        setScanning(false);
      }
    }
  }, [projectId, form, setForm, onRefresh]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!projectId) return;
    api.getModeSwitchImpact(projectId).then((data) => {
      setImpact(data);
      setImpactLoaded(true);
    }).catch(() => setImpactLoaded(true));
  }, [projectId]);

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
          </div>

          {form.local_path && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-medium text-text-tertiary">代码库概况</label>
                <button
                  type="button"
                  disabled={scanning || dirty}
                  onClick={() => startScan(!!form.codebase_summary)}
                  className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-text-secondary transition-colors hover:bg-bg-elevated disabled:opacity-40"
                >
                  {scanning ? (
                    <><RefreshCw size={11} className="animate-spin" /> {scanStage || '扫描中...'}</>
                  ) : form.codebase_summary ? (
                    <><RefreshCw size={11} /> 重新扫描</>
                  ) : (
                    <><ScanSearch size={11} /> 扫描代码库</>
                  )}
                </button>
              </div>
              {dirty && !form.codebase_summary && (
                <p className="text-[10px] text-amber-500">请先保存工作目录配置再扫描</p>
              )}
              {scanError && (
                <div className="flex items-center gap-2 rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2">
                  <AlertCircle size={12} className="flex-shrink-0 text-red-500" />
                  <p className="flex-1 text-[11px] text-red-500">{scanError}</p>
                  <button
                    onClick={() => startScan(true)}
                    className="flex-shrink-0 rounded-md border border-red-500/30 px-2 py-0.5 text-[10px] font-medium text-red-500 hover:bg-red-500/10"
                  >
                    重试
                  </button>
                </div>
              )}
              {scanning && scanContent && (
                <div className="max-h-64 overflow-y-auto rounded-md border border-accent/30 bg-bg-elevated p-3 text-xs leading-relaxed text-text-secondary">
                  <pre className="whitespace-pre-wrap font-sans">{scanContent}</pre>
                  <span className="inline-block h-3 w-1.5 animate-pulse bg-accent/60" />
                </div>
              )}
              {!scanning && (form.codebase_summary || scanContent) ? (
                <div className="max-h-64 overflow-y-auto rounded-md border border-border bg-bg-elevated p-3 text-xs leading-relaxed text-text-secondary prose-headings:text-text-primary prose-headings:font-semibold">
                  <pre className="whitespace-pre-wrap font-sans">{form.codebase_summary || scanContent}</pre>
                </div>
              ) : !scanning && !scanError && (
                <p className="text-[10px] text-text-muted">尚未扫描。点击扫描后，AI 将分析代码库结构并生成总结，供后续 Agent 交互使用。</p>
              )}
            </div>
          )}
        </div>

        {/* GitHub Integration */}
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

              {/* Clone prompt: show when connected but no local_path, unless dismissed */}
              {!form.local_path && ghCloneStep !== 'dismissed' && ghCloneStep !== 'cloning' && ghCloneStep !== 'done' && (
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
                      onClick={() => setShowFolderPicker(true)}
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
                  <span className="text-[11px] text-text-secondary">已关联: <code className="text-[10px]">{form.local_path}</code></span>
                </div>
              )}

              {ghWebhookUrl && (
                <div className="rounded-md border border-border/50 px-3 py-2">
                  <p className="text-[10px] text-text-muted">Webhook URL (在 GitHub 仓库 Settings → Webhooks 中配置)</p>
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
                value={form.repo_url}
                onChange={(v) => setForm({ ...form, repo_url: v })}
                placeholder="https://github.com/owner/repo"
              />
              <div>
                <label className="mb-1 block text-[11px] font-medium text-text-tertiary">Personal Access Token</label>
                <p className="mb-2 text-[10px] text-text-muted">
                  需要 <code className="rounded bg-bg-elevated px-1">repo</code> 权限。
                  <a href="https://github.com/settings/tokens/new?scopes=repo&description=Arc+Workstation" target="_blank" rel="noopener noreferrer" className="ml-1 text-accent hover:underline">
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
                    disabled={!ghToken.trim() || ghConnecting || !form.repo_url?.trim()}
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

        {/* Execution Mode */}
        <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
          <p className="mb-3 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">执行模式</p>
          <p className="mb-3 text-[11px] text-text-muted">决定项目中需求的推进方式。新创建的需求将继承此设置。</p>

          {/* Impact warning */}
          {impactLoaded && impact && impact.active_count > 0 && (
            <div className="mb-3 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
              <AlertTriangle size={13} className="mt-0.5 flex-shrink-0 text-amber-500" />
              <div className="text-[11px] text-amber-600">
                <span className="font-medium">当前有 {impact.active_count} 个进行中的需求</span>
                {impact.pending_count > 0 && <span>，{impact.pending_count} 个待启动的需求</span>}
                <span>。切换模式仅影响新建需求，已有需求保持原有模式不变。</span>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {(['pipeline', 'conversation'] as ExecutionMode[]).map((mode) => {
              const isActive = form.execution_mode === mode;
              const Icon = mode === 'pipeline' ? Workflow : MessageSquare;
              return (
                <button
                  key={mode}
                  onClick={() => setForm({ ...form, execution_mode: mode })}
                  className={`flex items-start gap-3 rounded-lg border-2 p-4 text-left transition-all ${
                    isActive
                      ? 'border-accent bg-accent/5'
                      : 'border-border hover:border-border-active hover:bg-bg-elevated'
                  }`}
                >
                  <div className={`mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${
                    isActive ? 'bg-accent text-white' : 'bg-bg-elevated text-text-muted'
                  }`}>
                    <Icon size={16} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium ${isActive ? 'text-accent' : 'text-text-primary'}`}>
                        {EXECUTION_MODE_LABELS[mode]}
                      </span>
                      {isActive && (
                        <span className="rounded-full bg-accent/15 px-1.5 py-0.5 text-[9px] font-medium text-accent">
                          当前
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-[11px] leading-relaxed text-text-muted">
                      {EXECUTION_MODE_DESCRIPTIONS[mode]}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Autopilot */}
        <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                isAutopilot ? 'bg-accent text-white' : 'bg-bg-elevated text-text-muted'
              }`}>
                <Zap size={16} />
              </div>
              <div>
                <p className="text-xs font-medium text-text-primary">自驾模式</p>
                <p className="text-[11px] text-text-muted">
                  {form.execution_mode === 'pipeline'
                    ? 'AI 自动通过阶段关卡，仅在异常时中断'
                    : 'Agent 完全自主推进，仅在异常时中断'}
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                setForm({
                  ...form,
                  pipeline_config: { ...form.pipeline_config, auto_advance: !isAutopilot },
                  conversation_config: { ...form.conversation_config, agent_autonomy: isAutopilot ? 'supervised' : 'full' },
                });
              }}
              className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
                isAutopilot ? 'bg-accent' : 'bg-border'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                isAutopilot ? 'translate-x-5' : ''
              }`} />
            </button>
          </div>
        </div>

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
        onSelect={(path) => setForm({ ...form, local_path: path })}
        initialPath={form.local_path || '~'}
      />
    </section>
  );
}
