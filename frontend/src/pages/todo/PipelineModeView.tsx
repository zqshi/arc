import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  Sparkles,
  Play,
  FileText,
  Loader2,
  Edit3,
  ChevronRight,
} from 'lucide-react';
import { useConversationSocket } from '../../hooks/useConversationSocket';
import { useToast } from '../../components/Toast';
import { api, ApiError } from '../../api/client';
import ArtifactRenderer from '../../components/artifact-renderers';
import ArtifactEditor from '../../components/artifact-renderers/ArtifactEditor';
import AgentExecutionPanel from '../../components/AgentExecutionPanel';
import ExperienceDetailModal from '../../components/ExperienceDetailModal';
import { ChatInput, ChatMessages, SmartActionBar, QuickPrompts } from '../../components/todo';
import type {
  Todo,
  PipelineState,
  PhaseType,
  PhaseStatus,
  Experience,
} from '../../types/api';
import { PHASE_ORDER, PHASE_LABELS, AGENT_EXECUTION_PHASES } from '../../types/api';

const PHASES_NO_SKIP: Set<PhaseType> = new Set([
  'clarification', 'architecture', 'development', 'testing', 'deployment', 'extraction',
]);

const PHASE_ICONS: Record<PhaseType, string> = {
  clarification: '1', ui_design: '2', architecture: '3', development: '4',
  testing: '5', deployment: '6', extraction: '7',
};

const PHASE_STATUS_STYLE: Record<PhaseStatus, string> = {
  pending: 'border-border text-text-muted bg-transparent',
  active: 'border-accent bg-accent text-white',
  awaiting_confirm: 'border-[#E5A93D] bg-[#E5A93D] text-white',
  confirmed: 'border-status-done bg-status-done text-white',
  skipped: 'border-border bg-bg-elevated text-text-muted line-through',
};

export function PipelineModeView({ todo, setTodo, isNarrow, isCompact }: {
  todo: Todo; setTodo: (t: Todo) => void; isNarrow: boolean; isCompact: boolean;
}) {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();

  const [pipeline, setPipeline] = useState<PipelineState | null>(null);
  const [activePhase, setActivePhase] = useState<PhaseType>('clarification');
  const [pipelineLoading, setPipelineLoading] = useState(true);
  const [editingArtifact, setEditingArtifact] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [relatedExps, setRelatedExps] = useState<Experience[]>([]);
  const [selectedExp, setSelectedExp] = useState<Experience | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(isNarrow);
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

  const fetchTodo = useCallback(async () => {
    if (!id) return;
    try { const data = await api.getTodo(id); setTodo(data); } catch {}
  }, [id, setTodo]);

  useEffect(() => { fetchPipeline(); }, [fetchPipeline]);

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
          const gapText = gate.gaps?.length ? gate.gaps.map((g: string) => `• ${g}`).join('\n') : '';
          const msg = `**门禁未通过** (${gate.score}/10)\n\n${gapText}\n\n${gate.suggestion}`;
          wsSocketRef.current.setMessages((prev) => [
            ...prev,
            { id: `gate-${Date.now()}`, conversation_id: currentPhaseData?.conversation_id || '', role: 'assistant' as const, content: msg, created_at: new Date().toISOString() },
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

  const pipelineInitialized = pipeline && pipeline.phases.length > 0;

  return (
    <>
      {/* Phase stepper bar */}
      {pipelineInitialized && (
        <div className="flex items-center gap-1 overflow-x-auto border-b border-border px-4 py-2">
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
          <span className="ml-2 text-[10px] text-text-muted">{PHASE_LABELS[activePhase]}</span>
        </div>
      )}

      {/* Main two-panel */}
      <div className={`flex flex-1 overflow-hidden ${isCompact ? 'flex-col' : ''}`}>
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
    </>
  );
}
