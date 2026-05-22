import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  FileText,
  Lightbulb,
  Loader2,
  ChevronRight,
  CheckCircle2,
  Circle,
} from 'lucide-react';
import { useConversationSocket } from '../../hooks/useConversationSocket';
import { useToast } from '../../components/Toast';
import { api } from '../../api/client';
import ExperienceDetailModal from '../../components/ExperienceDetailModal';
import DeliverableDrawer from '../../components/DeliverableDrawer';
import { ChatInput, ChatMessages } from '../../components/todo';
import type {
  Todo,
  Experience,
  DeliverableTracker,
  Conversation,
  Artifact,
} from '../../types/api';

const DELIVERABLE_LABELS: Record<string, string> = {
  requirement_spec: '需求规格',
  ui_design: 'UI设计',
  tech_architecture: '技术架构',
  dev_report: '开发报告',
  test_report: '测试报告',
  deploy_report: '部署报告',
  experience_card: '经验卡片',
};

export function ConversationModeView({ todo, setTodo, isNarrow, isCompact }: {
  todo: Todo; setTodo: (t: Todo) => void; isNarrow: boolean; isCompact: boolean;
}) {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const [inputValue, setInputValue] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [tracker, setTracker] = useState<DeliverableTracker | null>(null);
  const [initializing, setInitializing] = useState(false);
  const [showRight, setShowRight] = useState(!isNarrow);
  const [relatedExps, setRelatedExps] = useState<Experience[]>([]);
  const [selectedExp, setSelectedExp] = useState<Experience | null>(null);
  const [drawerArtifact, setDrawerArtifact] = useState<Artifact | null>(null);

  const {
    messages: wsMessages,
    isConnected,
    isStreaming,
    error: wsError,
    sendMessage: wsSend,
    retry: wsRetry,
    retryDisabled: wsRetryDisabled,
  } = useConversationSocket(conversationId);

  const fetchTracker = useCallback(async () => {
    if (!id) return;
    try {
      const state = await api.getDeliverables(id);
      setTracker(state);
    } catch {}
  }, [id]);

  const autoInitRef = useRef(false);

  const fetchConversation = useCallback(async () => {
    if (!id) return;
    try {
      const conversations = await api.listConversations(id);
      const unified = conversations.find((c: Conversation) => c.purpose === 'unified');
      if (unified) {
        setConversationId(unified.id);
      } else if (!autoInitRef.current) {
        autoInitRef.current = true;
        setInitializing(true);
        try {
          const updated = await api.startConversation(id);
          setTodo(updated);
          const convs = await api.listConversations(id);
          const newUnified = convs.find((c: Conversation) => c.purpose === 'unified');
          if (newUnified) setConversationId(newUnified.id);
          await fetchTracker();
        } catch (err) {
          toast(`初始化对话失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
        } finally {
          setInitializing(false);
        }
      }
    } catch {}
  }, [id, fetchTracker, toast, setTodo]);

  useEffect(() => {
    fetchConversation();
    fetchTracker();
  }, [fetchConversation, fetchTracker]);

  useEffect(() => {
    if (!todo) return;
    api.searchExperiences(todo.title, todo.project_id || undefined)
      .then(setRelatedExps).catch(() => setRelatedExps([]));
  }, [todo?.title]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isStreaming && conversationId) fetchTracker();
  }, [isStreaming, conversationId, fetchTracker]);

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    wsSend(trimmed);
    setInputValue('');
  };

  const isReady = !!conversationId;

  return (
    <>
      <div className="flex flex-1 overflow-hidden">
        {/* Center: Chat */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {isReady ? (
            <>
              {tracker && (
                <div className="flex items-center gap-2 border-b border-border/50 px-4 py-1.5">
                  <div className="h-1 w-20 overflow-hidden rounded-full bg-border">
                    <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${tracker.completion_pct * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-text-muted">{Math.round(tracker.completion_pct * 100)}%</span>
                </div>
              )}
              <div className="flex-1 overflow-y-auto px-4 py-3">
                <ChatMessages
                  messages={wsMessages}
                  isStreaming={isStreaming}
                  error={wsError}
                  conversationId={conversationId}
                  todoId={id!}
                  onRetry={wsRetry}
                  retryDisabled={wsRetryDisabled}
                />
              </div>
              <div className="border-t border-border px-4 py-2.5">
                <ChatInput value={inputValue} onChange={setInputValue} onSend={handleSend} disabled={!isConnected} />
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <Loader2 size={20} className="animate-spin text-accent" />
                <span className="text-xs text-text-muted">{initializing ? '正在初始化对话...' : '加载中...'}</span>
              </div>
            </div>
          )}
        </div>

        {/* Right: Deliverables panel */}
        {!isCompact && (showRight ? (
          <div className="flex w-[260px] flex-shrink-0 flex-col border-l border-border bg-bg-sidebar">
            <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
              <div className="flex items-center gap-2">
                <FileText size={13} className="text-accent" />
                <span className="text-xs font-medium text-text-primary">交付物</span>
              </div>
              <button onClick={() => setShowRight(false)} className="flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary">
                <ChevronRight size={13} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-3">
              {tracker ? (
                <div className="space-y-2">
                  {tracker.required.map((type) => {
                    const status = tracker.deliverables[type];
                    const isDone = status === 'produced' || status === 'confirmed';
                    const isInProgress = status === 'in_progress';
                    return (
                      <button
                        key={type}
                        disabled={!isDone}
                        onClick={async () => {
                          if (!isDone || !id) return;
                          try {
                            const artifacts = await api.listArtifacts(id);
                            const match = artifacts.find((a) => a.artifact_type === type);
                            if (match) setDrawerArtifact(match);
                          } catch { /* ignore */ }
                        }}
                        className={`flex w-full items-center gap-2.5 rounded-md p-2.5 text-left transition-colors ${
                          isDone ? 'bg-status-done/5 hover:bg-status-done/10 cursor-pointer'
                          : isInProgress ? 'bg-accent/5 cursor-default'
                          : 'bg-bg-elevated cursor-default'
                        }`}
                      >
                        {isDone ? (
                          <CheckCircle2 size={14} className="flex-shrink-0 text-status-done" />
                        ) : isInProgress ? (
                          <Loader2 size={14} className="flex-shrink-0 animate-spin text-accent" />
                        ) : (
                          <Circle size={14} className="flex-shrink-0 text-text-muted" />
                        )}
                        <div className="min-w-0 flex-1">
                          <span className={`text-[11px] font-medium ${
                            isDone ? 'text-status-done' : isInProgress ? 'text-accent' : 'text-text-secondary'
                          }`}>
                            {DELIVERABLE_LABELS[type] || type}
                          </span>
                          {isDone ? (
                            <p className="text-[9px] text-text-muted">点击预览</p>
                          ) : isInProgress ? (
                            <p className="text-[9px] text-accent/70">生成中...</p>
                          ) : (
                            <p className="text-[9px] text-text-muted">待生成</p>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="text-[11px] text-text-muted">暂无交付物信息</p>
              )}
              {tracker && tracker.is_complete && (
                <div className="mt-4 rounded-md border border-status-done/30 bg-status-done/5 p-3 text-center">
                  <CheckCircle2 size={20} className="mx-auto mb-1 text-status-done" />
                  <p className="text-xs font-medium text-status-done">全部交付物已完成</p>
                </div>
              )}
            </div>

            {relatedExps.length > 0 && (
              <div className="border-t border-border px-3 pt-2 pb-3">
                <div className="mb-1 flex items-center gap-1 px-1">
                  <Lightbulb size={10} className="text-accent" />
                  <span className="text-[9px] font-medium text-text-tertiary">相关经验</span>
                </div>
                {relatedExps.slice(0, 2).map((exp) => (
                  <button key={exp.id} onClick={() => setSelectedExp(exp)} className="mb-1 w-full rounded px-1.5 py-1 text-left text-[10px] text-text-secondary transition-colors hover:bg-bg-elevated">
                    <span className="line-clamp-1">{exp.title}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex w-10 flex-shrink-0 flex-col items-center border-l border-border bg-bg-sidebar py-3">
            <button onClick={() => setShowRight(true)} title="展开交付物面板" className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-card hover:text-accent">
              <FileText size={14} />
            </button>
          </div>
        ))}
      </div>

      <ExperienceDetailModal experience={selectedExp} onClose={() => setSelectedExp(null)} />
      <DeliverableDrawer
        open={!!drawerArtifact}
        onClose={() => setDrawerArtifact(null)}
        content={drawerArtifact ? { type: 'artifact', data: drawerArtifact } : null}
      />
    </>
  );
}
