import { useState, useEffect, useRef, useCallback } from 'react';
import { Save, Lightbulb, Settings, FolderOpen, ScanSearch, RefreshCw, AlertCircle } from 'lucide-react';
import { GitHubSection } from './GitHubSection';
import { ExecutionModeSection } from './ExecutionModeSection';
import { Field } from './FormFields';
import { api, ApiError } from '../../api/client';
import type { ScanEvent } from '../../api/client';
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

  // Sync local scan state when parent refreshes project data (e.g. tab switch)
  useEffect(() => {
    if (initialScanStatus === 'completed' && scanning) {
      setScanning(false);
      setScanStage('');
    }
    if (initialScanStatus === 'error' && scanning) {
      setScanning(false);
      setScanError(scanErrorText || '扫描失败');
    }
  }, [initialScanStatus, scanErrorText]); // eslint-disable-line react-hooks/exhaustive-deps

  // Stabilize onRefresh to prevent useCallback/useEffect dependency storms
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

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
          onRefreshRef.current();
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
  }, [projectId]); // onRefresh via ref — no dependency needed

  // Auto-recover SSE subscription when component mounts and scan is running on server
  useEffect(() => {
    if (initialScanStatus === 'scanning' && projectId) {
      subscribeToScanStream();
      return () => { abortRef.current?.abort(); };
    }
    // Scan completed while tab was inactive — sync the result
    if (initialScanStatus === 'completed' && !form.codebase_summary) {
      onRefreshRef.current();
    }
  }, [initialScanStatus, projectId, subscribeToScanStream]);

  // When tab re-mounts, refresh project data to get latest scan_status
  useEffect(() => {
    onRefreshRef.current();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
            onRefreshRef.current();
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
  }, [projectId, form, setForm, subscribeToScanStream]); // onRefresh via ref

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
                  onClick={() => startScan(!!(form.codebase_summary || initialScanStatus === 'completed'))}
                  className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-text-secondary transition-colors hover:bg-bg-elevated disabled:opacity-40"
                >
                  {scanning ? (
                    <><RefreshCw size={11} className="animate-spin" /> {scanStage || '扫描中...'}</>
                  ) : form.codebase_summary || initialScanStatus === 'completed' ? (
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
              ) : !scanning && !scanError && initialScanStatus === 'completed' ? (
                <div className="flex items-center gap-2 rounded-md border border-border bg-bg-elevated px-3 py-2">
                  <RefreshCw size={11} className="animate-spin text-text-muted" />
                  <p className="text-[10px] text-text-muted">加载扫描结果...</p>
                </div>
              ) : !scanning && !scanError && (
                <p className="text-[10px] text-text-muted">尚未扫描。点击扫描后，AI 将分析代码库结构并生成总结，供后续 Agent 交互使用。</p>
              )}
            </div>
          )}
        </div>

        {/* GitHub Integration */}
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
          onSkipClone={handleGhSkipClone}
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

        {/* Git 同步 */}
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
                onClick={() => {
                  const gitSync = (form.conversation_config?.git_sync || {}) as Record<string, unknown>;
                  setForm({
                    ...form,
                    conversation_config: {
                      ...form.conversation_config,
                      git_sync: { ...gitSync, auto_commit: !gitSync.auto_commit },
                    },
                  });
                }}
                className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
                  (form.conversation_config?.git_sync as Record<string, unknown>)?.auto_commit ? 'bg-accent' : 'bg-border'
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  (form.conversation_config?.git_sync as Record<string, unknown>)?.auto_commit ? 'translate-x-5' : ''
                }`} />
              </button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-text-primary">自动推送</p>
                <p className="text-[11px] text-text-muted">提交后自动 git push 到远端</p>
              </div>
              <button
                onClick={() => {
                  const gitSync = (form.conversation_config?.git_sync || {}) as Record<string, unknown>;
                  setForm({
                    ...form,
                    conversation_config: {
                      ...form.conversation_config,
                      git_sync: { ...gitSync, auto_push: !gitSync.auto_push },
                    },
                  });
                }}
                className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
                  (form.conversation_config?.git_sync as Record<string, unknown>)?.auto_push ? 'bg-accent' : 'bg-border'
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  (form.conversation_config?.git_sync as Record<string, unknown>)?.auto_push ? 'translate-x-5' : ''
                }`} />
              </button>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-[11px] text-text-muted whitespace-nowrap">Commit 前缀</label>
              <input
                type="text"
                value={((form.conversation_config?.git_sync as Record<string, unknown>)?.commit_prefix as string) || 'feat'}
                onChange={(e) => {
                  const gitSync = (form.conversation_config?.git_sync || {}) as Record<string, unknown>;
                  setForm({
                    ...form,
                    conversation_config: {
                      ...form.conversation_config,
                      git_sync: { ...gitSync, commit_prefix: e.target.value },
                    },
                  });
                }}
                placeholder="feat"
                className="h-7 w-24 rounded-md border border-border bg-bg-input px-2 text-xs text-text-primary focus:border-border-active focus:outline-none"
              />
              <label className="text-[11px] text-text-muted whitespace-nowrap">目标分支</label>
              <input
                type="text"
                value={((form.conversation_config?.git_sync as Record<string, unknown>)?.target_branch as string) || ''}
                onChange={(e) => {
                  const gitSync = (form.conversation_config?.git_sync || {}) as Record<string, unknown>;
                  setForm({
                    ...form,
                    conversation_config: {
                      ...form.conversation_config,
                      git_sync: { ...gitSync, target_branch: e.target.value },
                    },
                  });
                }}
                placeholder="留空使用当前分支"
                className="h-7 flex-1 rounded-md border border-border bg-bg-input px-2 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
              />
            </div>
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
