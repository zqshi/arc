import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  Bot,
  Send,
  Play,
  CheckCircle,
  FileText,
  Lightbulb,
  Loader2,
  Edit3,
  ChevronRight,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  ChevronDown as ChevDown,
} from 'lucide-react';
import { useConversationSocket } from '../hooks/useConversationSocket';
import { useBreakpoint } from '../hooks/useMediaQuery';
import { useToast } from '../components/Toast';
import { api, ApiError } from '../api/client';
import ArtifactRenderer from '../components/artifact-renderers';
import ArtifactEditor from '../components/artifact-renderers/ArtifactEditor';
import AgentExecutionPanel from '../components/AgentExecutionPanel';
import ExperienceDetailModal from '../components/ExperienceDetailModal';
import MarkdownContent from '../components/MarkdownContent';
import { useCurrentProject } from '../contexts/CurrentProjectContext';
import type {
  Todo,
  PipelineState,
  PhaseType,
  PhaseStatus,
  Experience,
  ExperienceRef,
} from '../types/api';
import { PHASE_ORDER, PHASE_LABELS, STATUS_LABELS, AGENT_EXECUTION_PHASES } from '../types/api';

// ─── Phase icon mapping ──────────────────────────────────
const PHASES_NO_SKIP: Set<PhaseType> = new Set(['clarification', 'architecture', 'testing']);

const PHASE_ICONS: Record<PhaseType, string> = {
  clarification: '1',
  ui_design: '2',
  architecture: '3',
  development: '4',
  testing: '5',
  deployment: '6',
  extraction: '7',
};

const PHASE_DESCRIPTIONS: Record<PhaseType, string> = {
  clarification: '与AI对话明确需求边界与验收标准',
  ui_design: '产出交互原型与界面描述',
  architecture: '确定技术选型与系统设计',
  development: 'Agent自动编码实现功能',
  testing: '验证功能正确性与回归',
  deployment: '部署上线并验证环境',
  extraction: '沉淀可复用经验卡片',
};

const PHASE_STATUS_STYLE: Record<PhaseStatus, string> = {
  pending: 'border-border text-text-muted bg-transparent',
  active: 'border-accent bg-accent text-white',
  awaiting_confirm: 'border-[#E5A93D] bg-[#E5A93D] text-white',
  confirmed: 'border-status-done bg-status-done text-white',
  skipped: 'border-border bg-bg-elevated text-text-muted line-through',
};

export default function TodoDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { setProject: setCurrentProject } = useCurrentProject();
  const [todo, setTodo] = useState<Todo | null>(null);

  const fetchTodo = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api.getTodo(id);
      setTodo(data);
      if (data.project_id && data.project_name) {
        setCurrentProject({ id: data.project_id, name: data.project_name });
      }
    } catch {
      navigate('/');
    }
  }, [id, navigate]);

  // Pipeline state
  const [pipeline, setPipeline] = useState<PipelineState | null>(null);
  const [activePhase, setActivePhase] = useState<PhaseType>('clarification');
  const [pipelineLoading, setPipelineLoading] = useState(true);

  // Artifact state
  const [editingArtifact, setEditingArtifact] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Chat state
  const [inputValue, setInputValue] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Experience
  const [relatedExps, setRelatedExps] = useState<Experience[]>([]);
  const [selectedExp, setSelectedExp] = useState<Experience | null>(null);

  // Action loading
  const [actionLoading, setActionLoading] = useState(false);

  // Responsive
  const { isCompact, isNarrow } = useBreakpoint();

  // Chat panel collapse — default collapsed on narrow screens
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const chatInitRef = useRef(false);
  useEffect(() => {
    if (!chatInitRef.current) {
      chatInitRef.current = true;
      if (isNarrow) setChatCollapsed(true);
    }
  }, [isNarrow]);

  // Compact mode: tab between artifact/chat
  const [mobileTab, setMobileTab] = useState<'artifact' | 'chat'>('artifact');

  // Derived: current phase data
  const currentPhaseData = pipeline?.phases.find((p) => p.phase_type === activePhase);
  const currentArtifact = pipeline?.artifacts.find(
    (a) => currentPhaseData && a.phase_id === currentPhaseData.id,
  );

  // WebSocket for the active phase's conversation
  const {
    messages: wsMessages,
    setMessages: setWsMessages,
    isConnected,
    isStreaming,
    error: wsError,
    sendMessage: wsSend,
    retry: wsRetry,
    retryDisabled: wsRetryDisabled,
  } = useConversationSocket(currentPhaseData?.conversation_id || null);

  const wsSocketRef = useRef({ setMessages: setWsMessages });
  wsSocketRef.current.setMessages = setWsMessages;

  // ─── Data fetching ──────────────────────────────────────
  const fetchPipeline = useCallback(async () => {
    if (!id) return;
    setPipelineLoading(true);
    try {
      const data = await api.getPipeline(id);
      setPipeline(data);
      // Auto-select the current active phase
      const active = data.phases.find((p) => p.status === 'active' || p.status === 'awaiting_confirm');
      if (active) setActivePhase(active.phase_type as PhaseType);
      else if (data.current_phase) setActivePhase(data.current_phase as PhaseType);
    } catch {
      setPipeline(null);
    } finally {
      setPipelineLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchTodo();
    fetchPipeline();
  }, [fetchTodo, fetchPipeline]);
  useEffect(() => () => setCurrentProject(null), [setCurrentProject]);

  // Auto-initialize pipeline for todos without phases on first visit
  const autoInitRef = useRef(false);
  useEffect(() => {
    if (autoInitRef.current || pipelineLoading || !id || !todo) return;
    if (pipeline && pipeline.phases.length === 0) {
      autoInitRef.current = true;
      handleStartPipeline();
    }
  }, [pipelineLoading, pipeline, todo]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [wsMessages]);

  useEffect(() => {
    if (!todo) return;
    api.searchExperiences(todo.title, todo.project_id || undefined).then(setRelatedExps).catch(() => setRelatedExps([]));
  }, [todo?.title]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Actions ────────────────────────────────────────────
  const handleStartPipeline = async () => {
    if (!id) return;
    setActionLoading(true);
    try {
      await api.startPipeline(id);
      await api.startPhase(id, 'clarification');
      setActivePhase('clarification');
      await Promise.all([fetchPipeline(), fetchTodo()]);
      toast('Pipeline已启动，开始需求澄清', 'success');
    } catch (err) {
      toast(`启动失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartPhase = async () => {
    if (!id) return;
    setActionLoading(true);
    try {
      await api.startPhase(id, activePhase);
      await fetchPipeline();
      toast(`${PHASE_LABELS[activePhase]}已开始`, 'success');
    } catch (err) {
      toast(`启动失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    try {
      await api.generateArtifact(id, activePhase);
      await fetchPipeline();
      toast('产出物已生成', 'success');
    } catch (err) {
      toast(`生成失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setGenerating(false);
    }
  };

  const handleConfirmPhase = async () => {
    if (!id) return;
    setActionLoading(true);
    try {
      await api.confirmPhase(id, activePhase);
      const currentIdx = PHASE_ORDER.indexOf(activePhase);
      if (currentIdx < PHASE_ORDER.length - 1) {
        const nextPhase = PHASE_ORDER[currentIdx + 1];
        await api.startPhase(id, nextPhase);
        setActivePhase(nextPhase);
      }
      await Promise.all([fetchPipeline(), fetchTodo()]);
      toast(`${PHASE_LABELS[activePhase]}已确认，自动进入下一阶段`, 'success');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const detail = JSON.parse(err.detail);
        if (detail?.type === 'gate_failed' && detail?.gate) {
          const gate = detail.gate;
          const gapText = gate.gaps?.length
            ? gate.gaps.map((g: string) => `• ${g}`).join('\n')
            : '';
          const msg = `⚠️ **门禁未通过** (${gate.score}/10)\n\n${gapText}\n\n💡 ${gate.suggestion}`;
          injectGateMessage(msg);
          toast('产出物尚未达标，请根据提示补充', 'error');
        } else {
          toast(`确认失败: ${err.detail}`, 'error');
        }
      } else {
        toast(`确认失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
      }
    } finally {
      setActionLoading(false);
    }
  };

  const injectGateMessage = (content: string) => {
    wsSocketRef.current.setMessages((prev) => [
      ...prev,
      {
        id: `gate-${Date.now()}`,
        conversation_id: currentPhaseData?.conversation_id || '',
        role: 'assistant' as const,
        content,
        created_at: new Date().toISOString(),
      },
    ]);
  };

  const handleSkipPhase = async () => {
    if (!id) return;
    setActionLoading(true);
    try {
      await api.skipPhase(id, activePhase);
      const currentIdx = PHASE_ORDER.indexOf(activePhase);
      if (currentIdx < PHASE_ORDER.length - 1) {
        const nextPhase = PHASE_ORDER[currentIdx + 1];
        await api.startPhase(id, nextPhase);
        setActivePhase(nextPhase);
      }
      await Promise.all([fetchPipeline(), fetchTodo()]);
      toast(`${PHASE_LABELS[activePhase]}已跳过`, 'success');
    } catch (err) {
      toast(`跳过失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveArtifact = async (content: Record<string, unknown>) => {
    if (!id || !currentArtifact) return;
    try {
      await api.updateArtifact(id, currentArtifact.id, content);
      await fetchPipeline();
      setEditingArtifact(false);
      toast('已保存', 'success');
    } catch (err) {
      toast(`保存失败: ${err instanceof Error ? err.message : '格式错误'}`, 'error');
    }
  };

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    wsSend(trimmed);
    setInputValue('');
  };

  if (!todo) {
    return (
      <div className="flex h-full items-center justify-center text-text-secondary">
        任务不存在
      </div>
    );
  }

  const pipelineInitialized = pipeline && pipeline.phases.length > 0;

  return (
    <div className="flex h-full flex-col">
      {/* ─── Header with progress bar ─── */}
      <header className="flex items-center gap-3 border-b border-border px-4 py-3">
        <button
          onClick={() => {
            if (todo.project_id) navigate(`/project/${todo.project_id}`);
            else navigate('/');
          }}
          className="flex items-center gap-1 text-xs text-text-secondary transition-colors hover:text-text-primary"
        >
          <ArrowLeft size={14} />
        </button>
        <div className="h-4 w-px bg-border" />

        {/* Breadcrumb */}
        <div className="flex min-w-0 items-center gap-1 text-xs">
          {todo.project_name && (
            <>
              <button
                onClick={() => navigate(`/project/${todo.project_id}`)}
                className="flex-shrink-0 text-text-tertiary transition-colors hover:text-accent"
              >
                {todo.project_name}
              </button>
              <span className="text-text-muted">›</span>
            </>
          )}
          {todo.version_name && (
            <>
              <button
                onClick={() => navigate(`/project/${todo.project_id}`)}
                className="flex-shrink-0 text-text-tertiary transition-colors hover:text-accent"
              >
                {todo.version_name}
              </button>
              <span className="text-text-muted">›</span>
            </>
          )}
          <h1 className="min-w-0 flex-shrink truncate font-heading text-sm font-semibold text-text-primary">
            {todo.title}
          </h1>
        </div>

        <span
          className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
            todo.status === 'active'
              ? 'bg-accent/15 text-accent'
              : todo.status === 'done'
              ? 'bg-status-done/15 text-status-done'
              : todo.status === 'error'
              ? 'bg-status-error/15 text-status-error'
              : 'bg-text-muted/15 text-text-muted'
          }`}
        >
          {STATUS_LABELS[todo.status]}
        </span>

        {/* Phase progress dots */}
        {pipelineInitialized && (
          <div className="ml-auto flex items-center gap-1">
            {PHASE_ORDER.map((pt, i) => {
              const phase = pipeline.phases.find((p) => p.phase_type === pt);
              const status = phase?.status || 'pending';
              return (
                <div key={pt} className="flex items-center">
                  <button
                    onClick={() => setActivePhase(pt)}
                    title={`${PHASE_LABELS[pt]} — ${status}`}
                    className={`flex h-5 w-5 items-center justify-center rounded-full border text-[9px] font-bold transition-all ${
                      PHASE_STATUS_STYLE[status as PhaseStatus]
                    } ${activePhase === pt ? 'ring-2 ring-accent/30 ring-offset-1 ring-offset-bg-primary' : ''}`}
                  >
                    {status === 'confirmed' ? '✓' : PHASE_ICONS[pt]}
                  </button>
                  {i < PHASE_ORDER.length - 1 && (
                    <div
                      className={`mx-0.5 h-px w-3 ${
                        status === 'confirmed' ? 'bg-status-done' : 'bg-border'
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </header>

      {/* ─── Main layout ─── */}
      <div className={`flex flex-1 overflow-hidden ${isCompact ? 'flex-col' : ''}`}>
        {/* Phase navigation — vertical sidebar or horizontal scroll strip */}
        <div className={`${
          isCompact
            ? 'flex flex-shrink-0 items-center gap-1 overflow-x-auto border-b border-border bg-bg-sidebar px-2 py-1.5'
            : 'flex w-[140px] flex-shrink-0 flex-col border-r border-border bg-bg-sidebar py-2'
        }`}>
          {pipelineInitialized ? (
            PHASE_ORDER.map((pt) => {
              const phase = pipeline.phases.find((p) => p.phase_type === pt);
              if (!phase) return null;
              const isActivePhase = activePhase === pt;
              return (
                <button
                  key={phase.id}
                  onClick={() => setActivePhase(pt)}
                  className={`${isCompact ? 'flex-shrink-0 px-2.5 py-1' : 'mx-2 mb-0.5 px-2 py-1.5'} flex items-center gap-2 rounded-md text-left text-[11px] transition-colors ${
                    isActivePhase
                      ? 'bg-accent-subtle text-accent font-medium'
                      : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                  }`}
                >
                  <span
                    className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-[8px] font-bold ${
                      phase.status === 'confirmed'
                        ? 'bg-status-done text-white'
                        : phase.status === 'active' || phase.status === 'awaiting_confirm'
                        ? 'bg-accent text-white'
                        : phase.status === 'skipped'
                        ? 'bg-text-muted/30 text-text-muted'
                        : 'bg-border text-text-muted'
                    }`}
                  >
                    {phase.status === 'confirmed' ? '✓' : phase.status === 'skipped' ? '—' : PHASE_ICONS[pt]}
                  </span>
                  <span className={`${isCompact ? 'whitespace-nowrap' : 'truncate'}`}>{PHASE_LABELS[pt]}</span>
                </button>
              );
            })
          ) : (
            !isCompact && (
            <div className="flex flex-1 flex-col overflow-y-auto px-3 py-3">
              <p className="mb-2 text-[11px] font-medium text-text-secondary">Pipeline 七阶段</p>
              <div className="mb-3 space-y-1.5">
                {PHASE_ORDER.map((pt, i) => (
                  <div key={pt} className="flex items-start gap-2">
                    <span className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-border text-[8px] font-bold text-text-muted">
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <span className="text-[11px] font-medium text-text-primary">{PHASE_LABELS[pt]}</span>
                      <p className="text-[9px] leading-snug text-text-muted">{PHASE_DESCRIPTIONS[pt]}</p>
                    </div>
                  </div>
                ))}
              </div>
              <button
                onClick={handleStartPipeline}
                disabled={actionLoading}
                className="flex w-full items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-2 text-[11px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
              >
                {actionLoading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                启动 Pipeline
              </button>
            </div>
            )
          )}

          {/* Related experiences at bottom — hidden on compact */}
          {!isCompact && relatedExps.length > 0 && (
            <div className="mt-auto border-t border-border px-2 pt-2">
              <div className="mb-1 flex items-center gap-1 px-1">
                <Lightbulb size={10} className="text-accent" />
                <span className="text-[9px] font-medium text-text-tertiary">相关经验</span>
              </div>
              {relatedExps.slice(0, 2).map((exp) => (
                <button
                  key={exp.id}
                  onClick={() => setSelectedExp(exp)}
                  className="mb-1 w-full rounded px-1.5 py-1 text-left text-[10px] text-text-secondary transition-colors hover:bg-bg-elevated"
                >
                  <span className="line-clamp-1">{exp.title}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Center: Artifact panel — shown in non-compact always, in compact only when mobileTab=artifact */}
        {(!isCompact || mobileTab === 'artifact') && (
        <div className="flex flex-1 flex-col overflow-hidden">
          {pipelineInitialized ? (
            <>
              {/* Artifact header */}
              <div className="flex items-center justify-between border-b border-border px-5 py-2.5">
                <div className="flex items-center gap-2">
                  <FileText size={13} className="text-accent" />
                  <span className="text-xs font-medium text-text-primary">
                    {PHASE_LABELS[activePhase]} — 产出物
                  </span>
                  {currentArtifact && (
                    <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[9px] text-text-muted">
                      v{currentArtifact.version}
                      {currentArtifact.is_confirmed && ' · 已确认'}
                    </span>
                  )}
                </div>
                {currentArtifact && !editingArtifact && (
                  <button
                    onClick={() => setEditingArtifact(true)}
                    className="flex items-center gap-1 text-[11px] text-text-muted transition-colors hover:text-accent"
                  >
                    <Edit3 size={11} />
                    编辑
                  </button>
                )}
                {editingArtifact && (
                  <span className="text-[10px] text-text-muted">编辑模式</span>
                )}
              </div>

              {/* Artifact content */}
              <div className="flex-1 overflow-y-auto px-5 py-4">
                {editingArtifact ? (
                  currentArtifact && (
                    <ArtifactEditor
                      artifactType={currentArtifact.artifact_type}
                      content={currentArtifact.content}
                      onSave={handleSaveArtifact}
                      onCancel={() => setEditingArtifact(false)}
                    />
                  )
                ) : currentArtifact ? (
                  <div className="space-y-4">
                    {AGENT_EXECUTION_PHASES.has(activePhase) && (
                      <AgentExecutionPanel todoId={id!} phaseType={activePhase} />
                    )}
                    <ArtifactRenderer
                      artifactType={currentArtifact.artifact_type}
                      content={currentArtifact.content}
                    />
                  </div>
                ) : currentPhaseData?.status === 'active' ? (
                  AGENT_EXECUTION_PHASES.has(activePhase) ? (
                    <div className="space-y-4">
                      <AgentExecutionPanel todoId={id!} phaseType={activePhase} />
                      <div className="flex flex-col items-center justify-center pt-6 text-center">
                        <Sparkles size={24} className="mb-3 text-accent/40" />
                        <p className="mb-1 text-sm text-text-secondary">
                          可通过 Agent 自动执行，或在右侧与 AI 对话
                        </p>
                        <p className="text-[11px] text-text-muted">
                          Agent 执行完成后可生成{PHASE_LABELS[activePhase]}产出物
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center text-center">
                      <Sparkles size={24} className="mb-3 text-accent/40" />
                      <p className="mb-1 text-sm text-text-secondary">
                        与 AI 对话后，点击"生成产出物"
                      </p>
                      <p className="text-[11px] text-text-muted">
                        AI 将从对话中提取结构化的{PHASE_LABELS[activePhase]}文档
                      </p>
                    </div>
                  )
                ) : currentPhaseData?.status === 'pending' ? (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <p className="mb-3 text-sm text-text-secondary">此阶段尚未开始</p>
                    <button
                      onClick={handleStartPhase}
                      disabled={actionLoading}
                      className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
                    >
                      {actionLoading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                      开始{PHASE_LABELS[activePhase]}
                    </button>
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-text-muted">
                    {currentPhaseData?.status === 'skipped' ? '此阶段已跳过' : '暂无内容'}
                  </div>
                )}
              </div>

              {/* Smart action bar — AI-guided next step */}
              {pipelineInitialized && currentPhaseData && currentPhaseData.status !== 'confirmed' && currentPhaseData.status !== 'skipped' && (
                <SmartActionBar
                  phaseStatus={currentPhaseData.status as PhaseStatus}
                  phaseLabel={PHASE_LABELS[activePhase]}
                  hasArtifact={!!currentArtifact}
                  hasMessages={wsMessages.filter(m => m.role !== 'system').length > 0}
                  canSkip={!PHASES_NO_SKIP.has(activePhase)}
                  actionLoading={actionLoading}
                  generating={generating}
                  onStartPhase={handleStartPhase}
                  onGenerate={handleGenerate}
                  onConfirm={handleConfirmPhase}
                  onSkip={handleSkipPhase}
                />
              )}
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center">
              {pipelineLoading ? (
                <Loader2 size={20} className="animate-spin text-accent" />
              ) : (
                <div className="text-center">
                  <p className="mb-1 text-sm text-text-secondary">{todo.description || '暂无描述'}</p>
                  <p className="mb-4 text-[11px] text-text-muted">启动 Pipeline 开始全链路交付流程</p>
                  <button
                    onClick={handleStartPipeline}
                    disabled={actionLoading}
                    className="flex items-center gap-1.5 rounded-md bg-accent px-5 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
                  >
                    {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                    启动 Pipeline
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        )}

        {/* Right: Chat panel — in compact mode shows as full-width tab, in desktop as collapsible side panel */}
        {isCompact ? (
          mobileTab === 'chat' && (
          <div className="flex flex-1 flex-col overflow-hidden bg-bg-elevated">
            <div className="flex-1 overflow-y-auto px-4 py-3">
              {wsMessages.filter((m) => m.role !== 'system').length > 0 ? (
                <div className="flex flex-col gap-3">
                  {wsMessages
                    .filter((msg) => msg.role !== 'system')
                    .map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                      >
                        {msg.role === 'assistant' && (
                          <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md bg-accent/15">
                            <Bot size={11} className="text-accent" />
                          </div>
                        )}
                        <div className="max-w-[85%]">
                          <div
                            className={`rounded-lg px-3 py-2 text-xs leading-relaxed ${
                              msg.role === 'assistant'
                                ? 'bg-bg-card text-text-secondary'
                                : 'bg-accent-subtle text-text-primary'
                            }`}
                          >
                            {msg.role === 'assistant' ? (
                              <MarkdownContent content={msg.content} />
                            ) : (
                              <div className="whitespace-pre-wrap">{msg.content}</div>
                            )}
                          </div>
                          {msg.role === 'assistant' && Array.isArray(msg.metadata?.referenced_experiences) && (
                            <ExperienceRefBadge
                              refs={msg.metadata.referenced_experiences as ExperienceRef[]}
                              todoId={id!}
                            />
                          )}
                        </div>
                      </div>
                    ))}
                  {isStreaming && (
                    <div className="flex gap-2">
                      <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md bg-accent/15">
                        <Bot size={11} className="text-accent animate-pulse" />
                      </div>
                      <span className="text-[11px] text-text-muted">思考中...</span>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center px-2 text-center">
                  <Bot size={20} className="mb-2 text-accent/30" />
                  <p className="text-[11px] text-text-muted">
                    {currentPhaseData?.conversation_id
                      ? '对话即将开始...'
                      : '启动阶段后可与AI对话'}
                  </p>
                </div>
              )}
            </div>
            {currentPhaseData?.conversation_id && (
              <div className="border-t border-border px-4 py-2.5">
                <ChatInput
                  value={inputValue}
                  onChange={setInputValue}
                  onSend={handleSend}
                  disabled={!isConnected}
                />
              </div>
            )}
          </div>
          )
        ) : chatCollapsed ? (
          <div className="flex w-10 flex-shrink-0 flex-col items-center border-l border-border bg-bg-elevated py-3">
            <button
              onClick={() => setChatCollapsed(false)}
              title="展开对话面板"
              className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-card hover:text-accent"
            >
              <Sparkles size={14} />
            </button>
          </div>
        ) : (
        <div className="flex w-[340px] flex-shrink-0 flex-col border-l border-border bg-bg-elevated">
          {/* Chat header */}
          <div className="border-b border-border px-4 py-2.5">
            <div className="flex items-center gap-2">
              <Sparkles size={13} className="text-accent" />
              <span className="text-xs font-medium text-text-primary">
                AI · {PHASE_LABELS[activePhase]}
              </span>
              {isConnected && (
                <span className="h-1.5 w-1.5 rounded-full bg-status-done" title="已连接" />
              )}
              <button
                onClick={() => setChatCollapsed(true)}
                title="收起对话面板"
                className="ml-auto flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary"
              >
                <ChevronRight size={13} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3">
            {wsMessages.filter((m) => m.role !== 'system').length > 0 ? (
              <div className="flex flex-col gap-3">
                {wsMessages
                  .filter((msg) => msg.role !== 'system')
                  .map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                    >
                      {msg.role === 'assistant' && (
                        <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md bg-accent/15">
                          <Bot size={11} className="text-accent" />
                        </div>
                      )}
                      <div className="max-w-[85%]">
                        <div
                          className={`rounded-lg px-3 py-2 text-xs leading-relaxed ${
                            msg.role === 'assistant'
                              ? 'bg-bg-card text-text-secondary'
                              : 'bg-accent-subtle text-text-primary'
                          }`}
                        >
                          {msg.role === 'assistant' ? (
                            <MarkdownContent content={msg.content} />
                          ) : (
                            <div className="whitespace-pre-wrap">{msg.content}</div>
                          )}
                        </div>
                        {msg.role === 'assistant' && Array.isArray(msg.metadata?.referenced_experiences) && (
                          <ExperienceRefBadge
                            refs={msg.metadata.referenced_experiences as ExperienceRef[]}
                            todoId={id!}
                          />
                        )}
                      </div>
                    </div>
                  ))}
                {isStreaming && (
                  <div className="flex gap-2">
                    <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md bg-accent/15">
                      <Bot size={11} className="text-accent animate-pulse" />
                    </div>
                    <span className="text-[11px] text-text-muted">思考中...</span>
                  </div>
                )}
                {wsError && (
                  <div className="mx-1 rounded-md border border-status-error/30 bg-status-error/5 px-3 py-2">
                    <p className="text-[11px] text-status-error">
                      {wsError.includes('暂时不可用')
                        ? '⚡ AI 服务暂时过载，请稍后重试'
                        : wsError.includes('超时')
                        ? '⏱ AI 响应超时，请简化问题后重试'
                        : `⚠ ${wsError}`}
                    </p>
                    <button
                      onClick={wsRetry}
                      disabled={isStreaming || wsRetryDisabled}
                      className="mt-1.5 flex items-center gap-1 rounded-md bg-status-error/10 px-2.5 py-1 text-[11px] font-medium text-status-error transition-colors hover:bg-status-error/20 disabled:opacity-50"
                    >
                      <RefreshCw size={11} className={wsRetryDisabled ? 'animate-spin' : ''} />
                      {wsRetryDisabled ? '请求中...' : '重新生成'}
                    </button>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center px-2 text-center">
                <Bot size={20} className="mb-2 text-accent/30" />
                <p className="text-[11px] text-text-muted">
                  {currentPhaseData?.conversation_id
                    ? '对话即将开始...'
                    : currentPhaseData?.status === 'active'
                    ? '阶段已就绪，等待连接...'
                    : '启动阶段后可与AI对话'}
                </p>
              </div>
            )}
          </div>

          {/* Quick prompts + Input */}
          {currentPhaseData?.conversation_id && (
            <div className="border-t border-border">
              {/* Quick prompts — show when user hasn't sent any message yet */}
              {wsMessages.filter((m) => m.role === 'user').length === 0 && (
                <QuickPrompts phase={activePhase} onSelect={(text) => { wsSend(text); }} />
              )}
              <div className="px-4 py-2.5">
                <ChatInput
                  value={inputValue}
                  onChange={setInputValue}
                  onSend={handleSend}
                  disabled={!isConnected}
                />
              </div>
            </div>
          )}
        </div>
        )}
      </div>

      {/* Compact mode tab bar */}
      {isCompact && pipelineInitialized && (
        <div className="flex flex-shrink-0 border-t border-border bg-bg-sidebar">
          <button
            onClick={() => setMobileTab('artifact')}
            className={`flex flex-1 items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition-colors ${
              mobileTab === 'artifact' ? 'text-accent' : 'text-text-muted'
            }`}
          >
            <FileText size={13} />
            产出物
          </button>
          <button
            onClick={() => setMobileTab('chat')}
            className={`flex flex-1 items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition-colors ${
              mobileTab === 'chat' ? 'text-accent' : 'text-text-muted'
            }`}
          >
            <Sparkles size={13} />
            对话
            {isConnected && <span className="h-1.5 w-1.5 rounded-full bg-status-done" />}
          </button>
        </div>
      )}

      <ExperienceDetailModal experience={selectedExp} onClose={() => setSelectedExp(null)} />
    </div>
  );
}

// ─── Smart Action Bar ─────────────────────────────────────
// Computes the single best next action and displays it as a
// guided prompt, not a wall of buttons.

interface SmartActionBarProps {
  phaseStatus: PhaseStatus;
  phaseLabel: string;
  hasArtifact: boolean;
  hasMessages: boolean;
  canSkip: boolean;
  actionLoading: boolean;
  generating: boolean;
  onStartPhase: () => void;
  onGenerate: () => void;
  onConfirm: () => void;
  onSkip: () => void;
}

function SmartActionBar({
  phaseStatus,
  phaseLabel,
  hasArtifact,
  hasMessages,
  canSkip,
  actionLoading,
  generating,
  onStartPhase,
  onGenerate,
  onConfirm,
  onSkip,
}: SmartActionBarProps) {
  let hint = '';
  let primaryLabel = '';
  let primaryAction: (() => void) | null = null;
  let primaryIcon: React.ReactNode = null;
  let showSkip = false;

  if (phaseStatus === 'pending') {
    hint = `准备好了？开始${phaseLabel}阶段`;
    primaryLabel = `开始${phaseLabel}`;
    primaryAction = onStartPhase;
    primaryIcon = <Play size={12} />;
    showSkip = canSkip;
  } else if (phaseStatus === 'active' && !hasArtifact && !hasMessages) {
    hint = `在右侧与 AI 对话，讨论${phaseLabel}方案`;
    primaryLabel = '';
    primaryAction = null;
  } else if (phaseStatus === 'active' && !hasArtifact && hasMessages) {
    hint = '对话信息已积累，可以生成结构化产出物';
    primaryLabel = '生成产出物';
    primaryAction = onGenerate;
    primaryIcon = generating ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />;
    showSkip = canSkip;
  } else if (phaseStatus === 'active' && hasArtifact) {
    hint = '产出物已生成，审阅后确认进入下一阶段（需通过质量门禁）';
    primaryLabel = '确认并继续';
    primaryAction = onConfirm;
    primaryIcon = <CheckCircle size={12} />;
  } else if (phaseStatus === 'awaiting_confirm') {
    hint = '请审阅产出物，确认后自动推进';
    primaryLabel = '确认并继续';
    primaryAction = onConfirm;
    primaryIcon = <CheckCircle size={12} />;
  }

  return (
    <div className="flex items-center justify-between border-t border-border bg-bg-elevated/50 px-5 py-2.5">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent/10">
          <Sparkles size={10} className="text-accent" />
        </span>
        <span className="text-[11px] text-text-secondary">{hint}</span>
      </div>
      <div className="flex items-center gap-2">
        {showSkip && (
          <button
            onClick={onSkip}
            disabled={actionLoading}
            className="text-[11px] text-text-muted transition-colors hover:text-text-secondary disabled:opacity-30"
          >
            跳过
          </button>
        )}
        {primaryAction && (
          <button
            onClick={primaryAction}
            disabled={actionLoading || generating}
            className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {primaryIcon}
            {primaryLabel}
            {(phaseStatus === 'active' && hasArtifact) || phaseStatus === 'awaiting_confirm' ? (
              <ChevronRight size={11} />
            ) : null}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Quick Prompts ───────────────────────────────────────
const PHASE_QUICK_PROMPTS: Record<PhaseType, string[]> = {
  clarification: [
    '这是一个全新功能，从零开始',
    '这是对现有功能的优化改进',
    '先帮我梳理一下核心问题',
  ],
  ui_design: [
    '参考主流产品的设计模式',
    '优先移动端体验',
    '我有一些设计想法想讨论',
  ],
  architecture: [
    '用现有技术栈实现',
    '对性能要求比较高',
    '需要考虑后续扩展性',
  ],
  development: [
    '先从核心逻辑开始',
    '先写测试再实现',
    '有哪些可以复用的模块？',
  ],
  testing: [
    '重点测试核心流程',
    '帮我列出需要覆盖的场景',
    '有哪些边缘情况需要注意？',
  ],
  deployment: [
    '走标准部署流程',
    '需要灰度发布',
    '有什么需要提前准备的？',
  ],
  extraction: [
    '这次项目有不少值得记录的',
    '帮我总结关键决策点',
    '有哪些经验可以复用？',
  ],
};

function QuickPrompts({ phase, onSelect }: { phase: PhaseType; onSelect: (text: string) => void }) {
  const prompts = PHASE_QUICK_PROMPTS[phase];
  return (
    <div className="flex flex-wrap gap-1.5 px-4 pt-2.5">
      {prompts.map((text) => (
        <button
          key={text}
          onClick={() => onSelect(text)}
          className="rounded-full border border-border bg-bg-card px-2.5 py-1 text-[10px] text-text-secondary transition-colors hover:border-accent/30 hover:text-accent"
        >
          {text}
        </button>
      ))}
    </div>
  );
}

// ─── Experience Reference Badge ─────────────────────────

function ExperienceRefBadge({ refs, todoId }: { refs: ExperienceRef[]; todoId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, 'up' | 'down'>>({});
  const { toast } = useToast();

  if (!refs || refs.length === 0) return null;

  const handleFeedback = async (expId: string, helpful: boolean) => {
    try {
      await api.feedbackExperience(expId, todoId, helpful);
      setFeedbackGiven((prev) => ({ ...prev, [expId]: helpful ? 'up' : 'down' }));
    } catch {
      toast('反馈提交失败', 'error');
    }
  };

  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-accent/70 transition-colors hover:bg-accent/5 hover:text-accent"
      >
        <Lightbulb size={10} />
        参考了 {refs.length} 条经验
        <ChevDown size={10} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="mt-1 space-y-1 rounded-md border border-border/50 bg-bg-card p-2">
          {refs.map((ref) => (
            <div key={ref.id} className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <span className="text-[10px] text-text-secondary">{ref.title}</span>
                <span className={`ml-1.5 rounded px-1 py-0.5 text-[8px] font-medium ${
                  ref.scope === 'personal' ? 'bg-purple-500/15 text-purple-500' : 'bg-sky-500/15 text-sky-400'
                }`}>
                  {ref.scope === 'personal' ? '个人' : '项目'}
                </span>
              </div>
              {feedbackGiven[ref.id] ? (
                <span className="text-[9px] text-text-muted">
                  {feedbackGiven[ref.id] === 'up' ? '已标记有效' : '已标记无效'}
                </span>
              ) : (
                <div className="flex gap-1">
                  <button
                    onClick={() => handleFeedback(ref.id, true)}
                    className="rounded p-0.5 text-text-muted hover:bg-status-done/10 hover:text-status-done"
                    title="有效"
                  >
                    <ThumbsUp size={10} />
                  </button>
                  <button
                    onClick={() => handleFeedback(ref.id, false)}
                    className="rounded p-0.5 text-text-muted hover:bg-status-error/10 hover:text-status-error"
                    title="无效"
                  >
                    <ThumbsDown size={10} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Chat Input (auto-resize textarea) ───────────────────

function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        rows={1}
        placeholder="输入消息... (Shift+Enter 换行)"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className="w-full resize-none rounded-md border border-border bg-bg-input py-2 pl-3 pr-8 text-xs leading-relaxed text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none disabled:opacity-50"
      />
      <button
        onClick={onSend}
        disabled={disabled || !value.trim()}
        className="absolute bottom-2 right-2 text-text-muted transition-colors hover:text-accent disabled:opacity-30"
      >
        <Send size={13} />
      </button>
    </div>
  );
}
