import { useState, useEffect, useRef, useCallback } from 'react';
import { Save, Lightbulb, Settings, Workflow, MessageSquare, AlertTriangle, Zap, FolderOpen, ScanSearch, RefreshCw, AlertCircle } from 'lucide-react';
import { Field } from './FormFields';
import { api } from '../../api/client';
import type { ScanEvent } from '../../api/client';
import FolderPicker from '../FolderPicker';
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
}

export function SettingsTab({ projectId, form, setForm, dirty, onSave, onRefresh, insights, onAppendConvention }: SettingsTabProps) {
  const isAutopilot = Boolean(form.pipeline_config?.auto_advance) || form.conversation_config?.agent_autonomy === 'full';

  const [impact, setImpact] = useState<{ active_count: number; pending_count: number } | null>(null);
  const [impactLoaded, setImpactLoaded] = useState(false);
  const [showFolderPicker, setShowFolderPicker] = useState(false);

  // Scan state
  const [scanning, setScanning] = useState(false);
  const [scanStage, setScanStage] = useState('');
  const [scanContent, setScanContent] = useState('');
  const [scanError, setScanError] = useState('');
  const abortRef = useRef<AbortController | null>(null);

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

      api.scanCodebaseStream(projectId, (event: ScanEvent) => {
        switch (event.event) {
          case 'stage':
            setScanStage(event.message || '');
            break;
          case 'chunk':
            setScanContent((prev) => prev + (event.content || ''));
            break;
          case 'done':
            setScanContent(event.summary || '');
            setScanning(false);
            setScanStage('');
            onRefresh();
            break;
          case 'error':
            setScanError(event.detail || '扫描失败');
            setScanning(false);
            setScanStage('');
            break;
          case 'close':
            if (scanning) {
              setScanning(false);
            }
            break;
        }
      }, controller.signal);
    } catch (e: unknown) {
      setScanError(e instanceof Error ? e.message : '扫描启动失败');
      setScanning(false);
    }
  }, [projectId, form, setForm, onRefresh, scanning]);

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
          <Field label="代码仓库" value={form.repo_url} onChange={(v) => setForm({ ...form, repo_url: v })} placeholder="https://github.com/..." />
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
