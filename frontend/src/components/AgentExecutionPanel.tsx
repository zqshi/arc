import { useState, useEffect, useCallback, useRef } from 'react';
import { Bot, Loader2, XCircle, CheckCircle, AlertTriangle, RefreshCw, Terminal } from 'lucide-react';
import { api } from '../api/client';
import type { AgentSession, AgentTypeInfo, AgentSessionStatus, AgentEvent, PhaseType } from '../types/api';

const STATUS_CONFIG: Record<AgentSessionStatus, { label: string; color: string; icon: typeof Bot }> = {
  pending: { label: '准备中', color: 'text-text-muted', icon: Loader2 },
  running: { label: '执行中', color: 'text-accent', icon: Loader2 },
  paused: { label: '已暂停', color: 'text-[#E5A93D]', icon: AlertTriangle },
  completed: { label: '已完成', color: 'text-status-done', icon: CheckCircle },
  error: { label: '执行出错', color: 'text-status-error', icon: XCircle },
  cancelled: { label: '已取消', color: 'text-text-muted', icon: XCircle },
};

interface AgentExecutionPanelProps {
  todoId: string;
  phaseType: PhaseType;
  onSessionChange?: (session: AgentSession | null) => void;
}

export default function AgentExecutionPanel({ todoId, phaseType, onSessionChange }: AgentExecutionPanelProps) {
  const [session, setSession] = useState<AgentSession | null>(null);
  const [agents, setAgents] = useState<AgentTypeInfo[]>([]);
  const [defaultAgent, setDefaultAgent] = useState('');
  const [selectedAgent, setSelectedAgent] = useState('');
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [showLogs, setShowLogs] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getAvailableAgents().then((resp) => {
      setAgents(resp.agents);
      setDefaultAgent(resp.default);
      if (!selectedAgent) setSelectedAgent(resp.default);
    }).catch((err) => { console.warn('Failed to load agents:', err); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchSession = useCallback(async () => {
    try {
      const s = await api.getAgentSession(todoId, phaseType);
      setSession(s);
      onSessionChange?.(s);
    } catch {
      setSession(null);
      onSessionChange?.(null);
    }
  }, [todoId, phaseType, onSessionChange]);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  useEffect(() => {
    if (!session || session.status === 'completed' || session.status === 'error' || session.status === 'cancelled') {
      setPolling(false);
      return;
    }
    setPolling(true);
    const timer = setInterval(fetchSession, 5000);
    return () => clearInterval(timer);
  }, [session?.status, fetchSession]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchEvents = useCallback(async () => {
    try {
      const evts = await api.getAgentEvents(todoId, phaseType);
      setEvents(evts);
    } catch {
      // ignore
    }
  }, [todoId, phaseType]);

  useEffect(() => {
    if (!session) return;
    fetchEvents();
    if (session.status === 'running' || session.status === 'pending') {
      const timer = setInterval(fetchEvents, 5000);
      return () => clearInterval(timer);
    }
  }, [session?.status, fetchEvents]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  const handleExecute = async () => {
    setLoading(true);
    try {
      const s = await api.executeAgent(todoId, phaseType, selectedAgent || undefined);
      setSession(s);
      onSessionChange?.(s);
    } catch (err) {
      // error handled by caller
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    try {
      const s = await api.cancelAgent(todoId, phaseType);
      setSession(s);
      onSessionChange?.(s);
    } catch {
      // ignore
    }
  };

  const handleRetry = async () => {
    setSession(null);
    onSessionChange?.(null);
    await handleExecute();
  };

  if (!session) {
    return (
      <div className="rounded-lg border border-border bg-bg-card p-4">
        <div className="mb-3 flex items-center gap-2">
          <Bot size={14} className="text-accent" />
          <span className="text-xs font-medium text-text-primary">Agent 执行</span>
        </div>
        <div className="mb-3 flex items-center gap-2">
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="rounded-md border border-border bg-bg-input px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
          >
            {agents.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}{a.value === defaultAgent ? ' (默认)' : ''}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleExecute}
          disabled={loading || agents.length === 0}
          className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Bot size={12} />}
          开始执行
        </button>
        {agents.length === 0 && (
          <p className="mt-2 text-[10px] text-text-muted">未配置任何可用的 Coding Agent</p>
        )}
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[session.status];
  const StatusIcon = statusCfg.icon;
  const isActive = session.status === 'pending' || session.status === 'running' || session.status === 'paused';
  const isTerminal = session.status === 'completed' || session.status === 'error' || session.status === 'cancelled';

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot size={14} className="text-accent" />
          <span className="text-xs font-medium text-text-primary">Agent 执行</span>
          <span className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${statusCfg.color}`}>
            <StatusIcon size={10} className={isActive ? 'animate-spin' : ''} />
            {statusCfg.label}
          </span>
        </div>
        {polling && (
          <span className="text-[9px] text-text-muted">自动刷新中...</span>
        )}
      </div>

      <div className="mb-2 space-y-1 text-[11px] text-text-secondary">
        <p>Agent: <span className="font-medium">{session.agent_type}</span></p>
        {session.external_session_id && (
          <p>Session: <span className="font-mono text-[10px]">{session.external_session_id}</span></p>
        )}
        {session.started_at && (
          <p>开始: {new Date(session.started_at).toLocaleString()}</p>
        )}
        {session.completed_at && (
          <p>完成: {new Date(session.completed_at).toLocaleString()}</p>
        )}
        {session.error_reason && (
          <p className="text-status-error">错误: {session.error_reason}</p>
        )}
      </div>

      <div className="flex items-center gap-2">
        {isActive && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-1 rounded-md border border-border px-3 py-1 text-[11px] text-text-secondary transition-colors hover:bg-bg-elevated"
          >
            <XCircle size={11} />
            取消
          </button>
        )}
        {isTerminal && (
          <button
            onClick={handleRetry}
            disabled={loading}
            className="flex items-center gap-1 rounded-md bg-accent px-3 py-1 text-[11px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {loading ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
            重新执行
          </button>
        )}
        <button
          onClick={() => setShowLogs(!showLogs)}
          className="ml-auto flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary"
        >
          <Terminal size={10} />
          {showLogs ? '收起日志' : '展开日志'}
        </button>
      </div>

      {showLogs && events.length > 0 && (
        <div className="mt-3 max-h-48 overflow-y-auto rounded-md border border-border/50 bg-bg-primary p-2">
          {events.map((evt) => (
            <div key={evt.id} className="flex gap-2 border-b border-border/20 py-1.5 last:border-0">
              <span className="flex-shrink-0 text-[9px] tabular-nums text-text-muted">
                {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '--:--'}
              </span>
              <span className="whitespace-pre-wrap break-all text-[11px] leading-relaxed text-text-secondary">
                {evt.content}
              </span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      )}
      {showLogs && events.length === 0 && session && (
        <p className="mt-3 text-center text-[10px] text-text-muted">暂无执行日志</p>
      )}
    </div>
  );
}
