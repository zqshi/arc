import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  Play,
  FileText,
  Lightbulb,
  Loader2,
  Edit3,
  ChevronRight,
} from 'lucide-react';
import { useConversationSocket } from '../hooks/useConversationSocket';
import { useBreakpoint } from '../hooks/useMediaQuery';
import { useToast } from '../components/Toast';
import { api, ApiError } from '../api/client';
import ArtifactRenderer from '../components/artifact-renderers';
import ArtifactEditor from '../components/artifact-renderers/ArtifactEditor';
import AgentExecutionPanel from '../components/AgentExecutionPanel';
import ExperienceDetailModal from '../components/ExperienceDetailModal';
import { useCurrentProject } from '../contexts/CurrentProjectContext';
import { ChatInput, ChatMessages, SmartActionBar, QuickPrompts } from '../components/todo';
import { TodoDetailSkeleton } from '../components/Skeleton';
import type {
  Todo,
  PipelineState,
  PhaseType,
  PhaseStatus,
  Experience,
} from '../types/api';
import { PHASE_ORDER, PHASE_LABELS, STATUS_LABELS, AGENT_EXECUTION_PHASES } from '../types/api';

const PHASES_NO_SKIP: Set<PhaseType> = new Set([
  'clarification', 'architecture', 'development', 'testing', 'deployment', 'extraction',
]);

const PHASE_ICONS: Record<PhaseType, string> = {
  clarification: '1', ui_design: '2', architecture: '3', development: '4',
  testing: '5', deployment: '6', extraction: '7',
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
  const [todoLoading, setTodoLoading] = useState(true);

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
    } finally {
      setTodoLoading(false);
    }
  }, [id, navigate]);

  const [pipeline, setPipeline] = useState<PipelineState | null>(null);
  const [activePhase, setActivePhase] = useState<PhaseType>('clarification');
  const [pipelineLoading, setPipelineLoading] = useState(true);
  const [editingArtifact, setEditingArtifact] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [relatedExps, setRelatedExps] = useState<Experience[]>([]);
  const [selectedExp, setSelectedExp] = useState<Experience | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const { isCompact, isNarrow } = useBreakpoint();
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const chatInitRef = useRef(false);
  useEffect(() => {
    if (!chatInitRef.current) {
      chatInitRef.current = true;
      if (isNarrow) setChatCollapsed(true);
    }
  }, [isNarrow]);

  const [mobileTab, setMobileTab] = useState<'artifact' | 'chat'>('artifact');

  const currentPhaseData = pipeline?.phases.find((p) => p.phase_type === activePhase);
  const currentArtifact = pipeline?.artifacts.find(
    (a) => currentPhaseData && a.phase_id === currentPhaseData.id,
  );

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

  const fetchPipeline = useCallback(async () => {
    if (!id) return;
    setPipelineLoading(true);
    try {
      const data = await api.getPipeline(id);
      setPipeline(data);
      const active = data.phases.find((p) => p.status === 'active' || p.status === 'awaiting_confirm');
      if (active) setActivePhase(active.phase_type as PhaseType);
      else if (data.current_phase) setActivePhase(data.current_phase as PhaseType);
    } catch {
      setPipeline(null);
    } finally {
      setPipelineLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchTodo(); fetchPipeline(); }, [fetchTodo, fetchPipeline]);
  useEffect(() => () => setCurrentProject(null), [setCurrentProject]);

  const autoInitRef = useRef(false);
  useEffect(() => {
    if (autoInitRef.current || pipelineLoading || !id || !todo) return;
    if (pipeline && pipeline.phases.length === 0) {
      autoInitRef.current = true;
      handleStartPipeline();
    }
  }, [pipelineLoading, pipeline, todo]); // eslint-disable-line react-hooks/exhaustive-deps

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
          wsSocketRef.current.setMessages((prev) => [
            ...prev,
            {
              id: `gate-${Date.now()}`,
              conversation_id: currentPhaseData?.conversation_id || '',
              role: 'assistant' as const,
              content: msg,
              created_at: new Date().toISOString(),
            },
          ]);
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

  if (todoLoading || !todo) {
    return todoLoading ? (
      <TodoDetailSkeleton />
    ) : (
      <div className="flex h-full items-center justify-center text-text-secondary">
        任务不存在
      </div>
    );
  }

  const pipelineInitialized = pipeline && pipeline.phases.length > 0;

  return (
    <div className="flex h-full flex-col">
      {/* ─── Header ─── */}
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
        <div className="flex min-w-0 items-center gap-1 text-xs">
          {todo.project_name && (
            <>
              <button onClick={() => navigate(`/project/${todo.project_id}`)} className="flex-shrink-0 text-text-tertiary transition-colors hover:text-accent">{todo.project_name}</button>
              <span className="text-text-muted">›</span>
            </>
          )}
          {todo.version_name && (
            <>
              <button onClick={() => navigate(`/project/${todo.project_id}`)} className="flex-shrink-0 text-text-tertiary transition-colors hover:text-accent">{todo.version_name}</button>
              <span className="text-text-muted">›</span>
            </>
          )}
          <h1 className="min-w-0 flex-shrink truncate font-heading text-sm font-semibold text-text-primary">{todo.title}</h1>
        </div>
        <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
          todo.status === 'active' ? 'bg-accent/15 text-accent'
            : todo.status === 'done' ? 'bg-status-done/15 text-status-done'
            : todo.status === 'error' ? 'bg-status-error/15 text-status-error'
            : 'bg-text-muted/15 text-text-muted'
        }`}>
          {STATUS_LABELS[todo.status]}
        </span>
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
                    className={`flex h-5 w-5 items-center justify-center rounded-full border text-[9px] font-bold transition-all ${PHASE_STATUS_STYLE[status as PhaseStatus]} ${activePhase === pt ? 'ring-2 ring-accent/30 ring-offset-1 ring-offset-bg-primary' : ''}`}
                  >
                    {status === 'confirmed' ? '✓' : PHASE_ICONS[pt]}
                  </button>
                  {i < PHASE_ORDER.length - 1 && (
                    <div className={`mx-0.5 h-px w-3 ${status === 'confirmed' ? 'bg-status-done' : 'bg-border'}`} />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </header>

      {/* ─── Main layout ─── */}
      <div className={`flex flex-1 overflow-hidden ${isCompact ? 'flex-col' : ''}`}>
        {/* Phase sidebar */}
        <PhaseSidebar
          phases={pipelineInitialized ? pipeline.phases : []}
          activePhase={activePhase}
          onSelectPhase={setActivePhase}
          isCompact={isCompact}
          relatedExps={relatedExps}
          onSelectExp={setSelectedExp}
          onStartPipeline={handleStartPipeline}
          actionLoading={actionLoading}
        />

        {/* Center: Artifact panel */}
        {(!isCompact || mobileTab === 'artifact') && (
        <div className="flex flex-1 flex-col overflow-hidden">
          {pipelineInitialized ? (
            <>
              <div className="flex items-center justify-between border-b border-border px-5 py-2.5">
                <div className="flex items-center gap-2">
                  <FileText size={13} className="text-accent" />
                  <span className="text-xs font-medium text-text-primary">{PHASE_LABELS[activePhase]} — 产出物</span>
                  {currentArtifact && (
                    <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[9px] text-text-muted">
                      v{currentArtifact.version}{currentArtifact.is_confirmed && ' · 已确认'}
                    </span>
                  )}
                </div>
                {currentArtifact && !editingArtifact && (
                  <button onClick={() => setEditingArtifact(true)} className="flex items-center gap-1 text-[11px] text-text-muted transition-colors hover:text-accent">
                    <Edit3 size={11} /> 编辑
                  </button>
                )}
                {editingArtifact && <span className="text-[10px] text-text-muted">编辑模式</span>}
              </div>

              <div className="flex-1 overflow-y-auto px-5 py-4">
                {editingArtifact ? (
                  currentArtifact && (
                    <ArtifactEditor artifactType={currentArtifact.artifact_type} content={currentArtifact.content} onSave={handleSaveArtifact} onCancel={() => setEditingArtifact(false)} />
                  )
                ) : currentArtifact ? (
                  <div className="space-y-4">
                    {AGENT_EXECUTION_PHASES.has(activePhase) && <AgentExecutionPanel todoId={id!} phaseType={activePhase} />}
                    <ArtifactRenderer artifactType={currentArtifact.artifact_type} content={currentArtifact.content} />
                  </div>
                ) : currentPhaseData?.status === 'active' ? (
                  AGENT_EXECUTION_PHASES.has(activePhase) ? (
                    <div className="space-y-4">
                      <AgentExecutionPanel todoId={id!} phaseType={activePhase} />
                      <div className="flex flex-col items-center justify-center pt-6 text-center">
                        <Sparkles size={24} className="mb-3 text-accent/40" />
                        <p className="mb-1 text-sm text-text-secondary">可通过 Agent 自动执行，或在右侧与 AI 对话</p>
                        <p className="text-[11px] text-text-muted">Agent 执行完成后可生成{PHASE_LABELS[activePhase]}产出物</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center text-center">
                      <Sparkles size={24} className="mb-3 text-accent/40" />
                      <p className="mb-1 text-sm text-text-secondary">与 AI 对话后，点击"生成产出物"</p>
                      <p className="text-[11px] text-text-muted">AI 将从对话中提取结构化的{PHASE_LABELS[activePhase]}文档</p>
                    </div>
                  )
                ) : currentPhaseData?.status === 'pending' ? (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <p className="mb-3 text-sm text-text-secondary">此阶段尚未开始</p>
                    <button onClick={handleStartPhase} disabled={actionLoading} className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50">
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
                  <button onClick={handleStartPipeline} disabled={actionLoading} className="flex items-center gap-1.5 rounded-md bg-accent px-5 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50">
                    {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                    启动 Pipeline
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        )}

        {/* Right: Chat panel */}
        {isCompact ? (
          mobileTab === 'chat' && (
          <div className="flex flex-1 flex-col overflow-hidden bg-bg-elevated">
            <div className="flex-1 overflow-y-auto px-4 py-3">
              <ChatMessages messages={wsMessages} isStreaming={isStreaming} error={null} conversationId={currentPhaseData?.conversation_id || null} todoId={id!} onRetry={wsRetry} retryDisabled={wsRetryDisabled} />
            </div>
            {currentPhaseData?.conversation_id && (
              <div className="border-t border-border px-4 py-2.5">
                <ChatInput value={inputValue} onChange={setInputValue} onSend={handleSend} disabled={!isConnected} />
              </div>
            )}
          </div>
          )
        ) : chatCollapsed ? (
          <div className="flex w-10 flex-shrink-0 flex-col items-center border-l border-border bg-bg-elevated py-3">
            <button onClick={() => setChatCollapsed(false)} title="展开对话面板" className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-card hover:text-accent">
              <Sparkles size={14} />
            </button>
          </div>
        ) : (
        <div className="flex w-[340px] flex-shrink-0 flex-col border-l border-border bg-bg-elevated">
          <div className="border-b border-border px-4 py-2.5">
            <div className="flex items-center gap-2">
              <Sparkles size={13} className="text-accent" />
              <span className="text-xs font-medium text-text-primary">AI · {PHASE_LABELS[activePhase]}</span>
              {isConnected && <span className="h-1.5 w-1.5 rounded-full bg-status-done" title="已连接" />}
              <button onClick={() => setChatCollapsed(true)} title="收起对话面板" className="ml-auto flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary">
                <ChevronRight size={13} />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-3">
            <ChatMessages messages={wsMessages} isStreaming={isStreaming} error={wsError} conversationId={currentPhaseData?.conversation_id || null} todoId={id!} onRetry={wsRetry} retryDisabled={wsRetryDisabled} />
          </div>
          {currentPhaseData?.conversation_id && (
            <div className="border-t border-border">
              {wsMessages.filter((m) => m.role === 'user').length === 0 && (
                <QuickPrompts phase={activePhase} onSelect={(text) => { wsSend(text); }} />
              )}
              <div className="px-4 py-2.5">
                <ChatInput value={inputValue} onChange={setInputValue} onSend={handleSend} disabled={!isConnected} />
              </div>
            </div>
          )}
        </div>
        )}
      </div>

      {/* Compact mode tab bar */}
      {isCompact && pipelineInitialized && (
        <div className="flex flex-shrink-0 border-t border-border bg-bg-sidebar">
          <button onClick={() => setMobileTab('artifact')} className={`flex flex-1 items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition-colors ${mobileTab === 'artifact' ? 'text-accent' : 'text-text-muted'}`}>
            <FileText size={13} /> 产出物
          </button>
          <button onClick={() => setMobileTab('chat')} className={`flex flex-1 items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition-colors ${mobileTab === 'chat' ? 'text-accent' : 'text-text-muted'}`}>
            <Sparkles size={13} /> 对话
            {isConnected && <span className="h-1.5 w-1.5 rounded-full bg-status-done" />}
          </button>
        </div>
      )}

      <ExperienceDetailModal experience={selectedExp} onClose={() => setSelectedExp(null)} />
    </div>
  );
}

// ─── Phase Sidebar ──────────────────────────────────────

interface PhaseSidebarProps {
  phases: PipelineState['phases'];
  activePhase: PhaseType;
  onSelectPhase: (pt: PhaseType) => void;
  isCompact: boolean;
  relatedExps: Experience[];
  onSelectExp: (exp: Experience) => void;
  onStartPipeline: () => void;
  actionLoading: boolean;
}

function PhaseSidebar({ phases, activePhase, onSelectPhase, isCompact, relatedExps, onSelectExp, onStartPipeline, actionLoading }: PhaseSidebarProps) {
  const hasPhases = phases.length > 0;

  return (
    <div className={`${
      isCompact
        ? 'flex flex-shrink-0 items-center gap-1 overflow-x-auto border-b border-border bg-bg-sidebar px-2 py-1.5'
        : 'flex w-[140px] flex-shrink-0 flex-col border-r border-border bg-bg-sidebar py-2'
    }`}>
      {hasPhases ? (
        PHASE_ORDER.map((pt) => {
          const phase = phases.find((p) => p.phase_type === pt);
          if (!phase) return null;
          const isActive = activePhase === pt;
          return (
            <button
              key={phase.id}
              onClick={() => onSelectPhase(pt)}
              className={`${isCompact ? 'flex-shrink-0 px-2.5 py-1' : 'mx-2 mb-0.5 px-2 py-1.5'} flex items-center gap-2 rounded-md text-left text-[11px] transition-colors ${
                isActive ? 'bg-accent-subtle text-accent font-medium' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
              }`}
            >
              <span className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-[8px] font-bold ${
                phase.status === 'confirmed' ? 'bg-status-done text-white'
                  : phase.status === 'active' || phase.status === 'awaiting_confirm' ? 'bg-accent text-white'
                  : phase.status === 'skipped' ? 'bg-text-muted/30 text-text-muted'
                  : 'bg-border text-text-muted'
              }`}>
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
                <span className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-border text-[8px] font-bold text-text-muted">{i + 1}</span>
                <div className="min-w-0">
                  <span className="text-[11px] font-medium text-text-primary">{PHASE_LABELS[pt]}</span>
                  <p className="text-[9px] leading-snug text-text-muted">{PHASE_DESCRIPTIONS[pt]}</p>
                </div>
              </div>
            ))}
          </div>
          <button onClick={onStartPipeline} disabled={actionLoading} className="flex w-full items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-2 text-[11px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50">
            {actionLoading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            启动 Pipeline
          </button>
        </div>
        )
      )}

      {!isCompact && relatedExps.length > 0 && (
        <div className="mt-auto border-t border-border px-2 pt-2">
          <div className="mb-1 flex items-center gap-1 px-1">
            <Lightbulb size={10} className="text-accent" />
            <span className="text-[9px] font-medium text-text-tertiary">相关经验</span>
          </div>
          {relatedExps.slice(0, 2).map((exp) => (
            <button key={exp.id} onClick={() => onSelectExp(exp)} className="mb-1 w-full rounded px-1.5 py-1 text-left text-[10px] text-text-secondary transition-colors hover:bg-bg-elevated">
              <span className="line-clamp-1">{exp.title}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
