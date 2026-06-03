/**
 * UnifiedWorkspaceView — 统一对话工作区。
 *
 * 三个模式共用同一个界面布局：左侧对话 + 右侧交付物侧边栏。
 * 差异通过 processConstraint 控制侧边栏展示逻辑。
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useConversationSocket } from '../../hooks/useConversationSocket';
import type { ToolCallInfo } from '../../hooks/useConversationSocket';
import { ApprovalDialog } from '../../components/todo/ApprovalDialog';
import { CodeChangesReview } from '../../components/todo/CodeChangesReview';
import type { CodeChangesInfo } from '../../components/todo/CodeChangesReview';
import { ToolCallsLive, ToolCallsCollapsed, ToolCallsStreamingStatus } from '../../components/todo/ToolCallDisplay';
import { openPrototypeInNewTab } from '../../components/todo/prototypePreview';
import { WorkerProgress } from '../../components/todo/WorkerProgress';
import { DeliverableSidebar } from '../../components/todo/DeliverableSidebar';
import DeliverableDrawer from '../../components/DeliverableDrawer';
import { useToast } from '../../components/Toast';
import { api } from '../../api/client';
import { ChatInput, ChatMessages } from '../../components/todo';
import type {
  Todo,
  ProcessConstraint,
  DeliverableTracker,
  Conversation,
  Artifact,
} from '../../types/api';

interface Props {
  todo: Todo;
  setTodo: (t: Todo) => void;
  isNarrow: boolean;
  isCompact: boolean;
}

export function UnifiedWorkspaceView({ todo, setTodo, isNarrow, isCompact }: Props) {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const [inputValue, setInputValue] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [tracker, setTracker] = useState<DeliverableTracker | null>(null);
  const [initializing, setInitializing] = useState(false);
  const [drawerArtifact, setDrawerArtifact] = useState<Artifact | null>(null);
  const [drawerWidth, setDrawerWidth] = useState(480);
  const [codeChanges, setCodeChanges] = useState<CodeChangesInfo | null>(null);

  // 从 todo 或 project 获取 process_constraint
  const processConstraint: ProcessConstraint =
    (todo as unknown as Record<string, string>).process_constraint as ProcessConstraint
    || (todo.execution_mode === 'pipeline' ? 'strict' : 'free');

  // sidebar 默认展开状态：strict/moderate 默认展开，free 默认收起
  const [showSidebar, setShowSidebar] = useState(
    () => !isNarrow && processConstraint !== 'free'
  );

  const {
    messages: wsMessages,
    isConnected,
    isStreaming,
    error: wsError,
    sendMessage: wsSend,
    retry: wsRetry,
    retryDisabled: wsRetryDisabled,
    artifactsVersion,
    toolCalls,
    pendingApproval,
    respondToApproval,
    workers,
    orchestrationPhase,
  } = useConversationSocket(conversationId);

  // --- Data fetching ---

  const fetchTracker = useCallback(async () => {
    if (!id) return;
    try {
      const state = await api.getDeliverables(id);
      setTracker(state);
      if (state.is_complete) {
        try { const updated = await api.getTodo(id); setTodo(updated); } catch { /* */ }
      }
    } catch { /* */ }
  }, [id, setTodo]);

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
    } catch { /* */ }
  }, [id, fetchTracker, toast, setTodo]);

  useEffect(() => { fetchConversation(); fetchTracker(); }, [fetchConversation, fetchTracker]);
  useEffect(() => { if (!isStreaming && conversationId) fetchTracker(); }, [isStreaming, conversationId, fetchTracker]);
  useEffect(() => { if (artifactsVersion > 0) fetchTracker(); }, [artifactsVersion, fetchTracker]);
  useEffect(() => {
    if (!isStreaming || !conversationId) return;
    const interval = setInterval(fetchTracker, 8000);
    return () => clearInterval(interval);
  }, [isStreaming, conversationId, fetchTracker]);

  // Code changes detection
  useEffect(() => {
    const latest = wsMessages[wsMessages.length - 1];
    if (latest?.role === 'system' && latest?.metadata?.type === 'code_changes_ready' && !codeChanges) {
      const m = latest.metadata;
      setCodeChanges({
        todoId: id!,
        filesChanged: m.files_changed?.length || 0,
        insertions: m.insertions || 0,
        deletions: m.deletions || 0,
        diffStat: m.diff_stat || '',
        diffPreview: m.diff_preview || '',
      });
    }
  }, [wsMessages, id, codeChanges]);

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    wsSend(trimmed);
    setInputValue('');
  };

  const isReady = !!conversationId;

  // 确定 strict 模式的 currentPhase — 必须按 tracker.required 顺序查找第一个未完成项
  const currentPhase = tracker
    ? tracker.required.find((type) => {
        const status = tracker.deliverables[type];
        return !status || status === 'in_progress' || status === 'pending';
      })
    : undefined;

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Main: Chat */}
      <div className="flex flex-1 flex-col overflow-hidden" style={{ minWidth: 300 }}>
        {isReady ? (
          <>
            {/* Progress bar (non-free modes) */}
            {processConstraint !== 'free' && tracker && (
              <div className="flex items-center gap-2 border-b border-border/50 px-4 py-1.5">
                <div className="h-1 w-20 overflow-hidden rounded-full bg-border">
                  <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${tracker.completion_pct * 100}%` }} />
                </div>
                <span className="text-[10px] text-text-muted">{Math.round(tracker.completion_pct * 100)}%</span>
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3">
              <ChatMessages
                messages={wsMessages}
                isStreaming={isStreaming}
                error={wsError}
                conversationId={conversationId}
                todoId={id!}
                onRetry={wsRetry}
                retryDisabled={wsRetryDisabled}
                hideStreamingIndicator={toolCalls.length > 0}
              />
              {/* Approval dialog */}
              {pendingApproval && (
                <ApprovalDialog approval={pendingApproval} onRespond={respondToApproval} />
              )}
              {/* Worker progress */}
              {workers.length > 0 && (
                <WorkerProgress workers={workers} phase={orchestrationPhase} />
              )}
              {/* Tool calls — 实时展示工具执行过程 */}
              {isStreaming && toolCalls.length > 0 && (
                <ToolCallsLive toolCalls={toolCalls} />
              )}
              <ToolCallsStreamingStatus toolCalls={toolCalls} isStreaming={isStreaming} />
            </div>

            {/* Code changes */}
            {codeChanges && (
              <div className="border-t border-border px-4 py-2.5">
                <CodeChangesReview changes={codeChanges} onDismiss={() => setCodeChanges(null)} onPushComplete={() => setCodeChanges(null)} />
              </div>
            )}

            {/* Input */}
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

      {/* Deliverable detail drawer */}
      {drawerArtifact && (
        <DeliverableDrawer
          onClose={() => setDrawerArtifact(null)}
          content={{ type: 'artifact', data: drawerArtifact }}
          width={drawerWidth}
          onWidthChange={setDrawerWidth}
        />
      )}

      {/* Right: Sidebar */}
      {!isCompact && (
        <DeliverableSidebar
          constraint={processConstraint}
          tracker={tracker}
          todoId={id!}
          currentPhase={currentPhase}
          onItemClick={setDrawerArtifact}
          visible={showSidebar}
          onToggle={() => setShowSidebar(!showSidebar)}
        />
      )}
    </div>
  );
}
