/**
 * 工具调用分组显示组件 — 支持 parallel batch、serial batch、自动折叠。
 * 从 ConversationModeView 提取，职责单一：渲染 tool call 列表。
 */

import { useState, useEffect, useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import type { ToolCallInfo } from '../../hooks/useConversationSocket';

// ---------------------------------------------------------------------------
// Constants & types
// ---------------------------------------------------------------------------

const PARALLEL_INLINE_LIMIT = 5;
const LIVE_RECENT_LIMIT = 3;

type ToolCallGroup =
  | { kind: 'single'; item: ToolCallInfo }
  | { kind: 'parallel'; items: ToolCallInfo[] }
  | { kind: 'serial'; toolName: string; items: ToolCallInfo[] };

// ---------------------------------------------------------------------------
// Grouping logic
// ---------------------------------------------------------------------------

function toolCallLabel(tc: ToolCallInfo): string {
  const input = tc.tool_input as Record<string, string>;
  switch (tc.tool_name) {
    case 'read_file': return input.path || '';
    case 'list_directory': return input.path || '.';
    case 'grep_search': return `"${input.pattern || ''}"`;
    case 'run_command': return input.command || '';
    case 'write_file': return input.path || '';
    default: return '';
  }
}

function groupToolCalls(calls: ToolCallInfo[]): ToolCallGroup[] {
  const groups: ToolCallGroup[] = [];
  let parallelBatch: ToolCallInfo[] = [];
  let serialBatch: ToolCallInfo[] = [];
  let serialName = '';

  const flushSerial = () => {
    if (serialBatch.length >= 2) {
      groups.push({ kind: 'serial', toolName: serialName, items: [...serialBatch] });
    } else if (serialBatch.length === 1) {
      groups.push({ kind: 'single', item: serialBatch[0] });
    }
    serialBatch = [];
    serialName = '';
  };

  const flushParallel = () => {
    if (parallelBatch.length > 0) {
      groups.push({ kind: 'parallel', items: [...parallelBatch] });
      parallelBatch = [];
    }
  };

  for (const tc of calls) {
    if (tc.parallel) {
      flushSerial();
      parallelBatch.push(tc);
    } else {
      flushParallel();
      if (tc.tool_name === serialName) {
        serialBatch.push(tc);
      } else {
        flushSerial();
        serialName = tc.tool_name;
        serialBatch.push(tc);
      }
    }
  }
  flushParallel();
  flushSerial();
  return groups;
}

// ---------------------------------------------------------------------------
// Atomic components
// ---------------------------------------------------------------------------

function ToolCallRow({ tc }: { tc: ToolCallInfo }) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-0.5 text-[11px] rounded hover:bg-bg-elevated/60">
      <span className={`flex-shrink-0 text-[10px] ${
        tc.status === 'running' ? 'animate-pulse text-accent' : tc.is_error ? 'text-status-error' : 'text-status-done'
      }`}>
        {tc.status === 'running' ? '⟳' : tc.is_error ? '✗' : '✓'}
      </span>
      <span className="font-medium text-text-primary whitespace-nowrap">{tc.tool_name}</span>
      <span className="text-text-muted truncate min-w-0">{toolCallLabel(tc)}</span>
    </div>
  );
}

function ParallelProgress({ items }: { items: ToolCallInfo[] }) {
  const done = items.filter(tc => tc.status === 'done').length;
  const errors = items.filter(tc => tc.is_error).length;
  const pct = items.length > 0 ? (done / items.length) * 100 : 0;
  const allDone = done === items.length;
  const names = items.reduce<Record<string, number>>((acc, tc) => {
    acc[tc.tool_name] = (acc[tc.tool_name] || 0) + 1; return acc;
  }, {});
  const dominant = Object.entries(names).sort((a, b) => b[1] - a[1])[0];
  const label = dominant ? `${dominant[0]} ×${dominant[1]}` : `×${items.length}`;

  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="text-accent font-medium whitespace-nowrap">⚡ {label}</span>
      <div className="h-1 flex-1 min-w-12 max-w-24 rounded-full bg-border overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            errors > 0 ? 'bg-status-error' : allDone ? 'bg-status-done' : 'bg-accent'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`whitespace-nowrap ${allDone ? 'text-status-done' : 'text-text-muted'}`}>
        {done}/{items.length}{errors > 0 ? ` (${errors} 失败)` : allDone ? ' ✓' : ''}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Batch components
// ---------------------------------------------------------------------------

function ParallelBatch({ items, defaultExpanded }: { items: ToolCallInfo[]; defaultExpanded: boolean }) {
  const allDone = items.every(tc => tc.status === 'done');
  const needsCollapse = items.length > PARALLEL_INLINE_LIMIT;
  const [expanded, setExpanded] = useState(!needsCollapse ? true : defaultExpanded && !allDone);

  useEffect(() => {
    if (needsCollapse && allDone) setExpanded(false);
  }, [allDone, needsCollapse]);

  if (!needsCollapse) {
    return (
      <div className="rounded-lg border border-accent/15 bg-accent/[0.02] py-1 space-y-0.5">
        <div className="px-2.5 pb-0.5"><ParallelProgress items={items} /></div>
        {items.map(tc => <ToolCallRow key={tc.id} tc={tc} />)}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-accent/15 bg-accent/[0.02]">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full cursor-pointer items-center gap-2 px-2.5 py-1.5 select-none">
        <ParallelProgress items={items} />
        <span className="text-[10px] text-text-muted ml-auto whitespace-nowrap">{expanded ? '收起' : '点击展开'}</span>
      </button>
      {expanded && (
        <div className="max-h-[140px] overflow-y-auto border-t border-accent/10 py-0.5">
          {items.map(tc => <ToolCallRow key={tc.id} tc={tc} />)}
        </div>
      )}
    </div>
  );
}

function SerialBatch({ toolName, items, defaultExpanded }: { toolName: string; items: ToolCallInfo[]; defaultExpanded: boolean }) {
  const done = items.filter(tc => tc.status === 'done').length;
  const allDone = done === items.length;
  const errors = items.filter(tc => tc.is_error).length;
  const [expanded, setExpanded] = useState(defaultExpanded && !allDone);

  useEffect(() => { if (allDone) setExpanded(false); }, [allDone]);

  return (
    <div className="rounded-lg border border-border/40 bg-bg-elevated/30">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center gap-1.5 px-2 py-1 text-[11px] select-none">
        <span className={`flex-shrink-0 text-[10px] ${allDone ? (errors > 0 ? 'text-status-error' : 'text-status-done') : 'animate-pulse text-accent'}`}>
          {allDone ? (errors > 0 ? '✗' : '✓') : '⟳'}
        </span>
        <span className="font-medium text-text-primary">{toolName}</span>
        <span className="text-text-muted">×{items.length}</span>
        {errors > 0 && <span className="text-status-error text-[10px]">({errors} 失败)</span>}
        <span className="text-[10px] text-text-muted ml-auto">{expanded ? '收起' : '展开'}</span>
      </button>
      {expanded && (
        <div className="max-h-[120px] overflow-y-auto border-t border-border/30 py-0.5">
          {items.map(tc => <ToolCallRow key={tc.id} tc={tc} />)}
        </div>
      )}
    </div>
  );
}

function ToolCallGroupView({ group, defaultExpanded }: { group: ToolCallGroup; defaultExpanded: boolean }) {
  switch (group.kind) {
    case 'single': return <ToolCallRow tc={group.item} />;
    case 'parallel': return <ParallelBatch items={group.items} defaultExpanded={defaultExpanded} />;
    case 'serial': return <SerialBatch toolName={group.toolName} items={group.items} defaultExpanded={defaultExpanded} />;
  }
}

// ---------------------------------------------------------------------------
// Exported container components
// ---------------------------------------------------------------------------

export function ToolCallsLive({ toolCalls }: { toolCalls: ToolCallInfo[] }) {
  const grouped = useMemo(() => groupToolCalls(toolCalls), [toolCalls]);
  const totalDone = toolCalls.filter(tc => tc.status === 'done').length;
  const totalRunning = toolCalls.filter(tc => tc.status === 'running').length;

  const olderGroups: ToolCallGroup[] = [];
  const recentGroups: ToolCallGroup[] = [];
  let recentCount = 0;

  for (let i = grouped.length - 1; i >= 0; i--) {
    const g = grouped[i];
    const hasRunning = g.kind === 'single' ? g.item.status === 'running' : g.items.some(tc => tc.status === 'running');
    if (hasRunning || recentCount < LIVE_RECENT_LIMIT) { recentGroups.unshift(g); recentCount++; }
    else { olderGroups.push(g); }
  }
  olderGroups.reverse();

  const [showOlder, setShowOlder] = useState(false);
  const olderCallCount = olderGroups.reduce((n, g) => n + (g.kind === 'single' ? 1 : g.items.length), 0);

  return (
    <div className="mt-2 space-y-1 border-t border-border/50 pt-2">
      {olderCallCount > 0 && (
        <button onClick={() => setShowOlder(!showOlder)} className="flex items-center gap-1.5 px-2 py-1 text-[10px] text-text-muted hover:text-text-secondary select-none w-full">
          <span className="text-status-done">✓</span>
          <span>已完成 {totalDone - totalRunning > 0 ? totalDone : olderCallCount} 个工具调用</span>
          <span className="ml-auto">{showOlder ? '收起' : '展开'}</span>
        </button>
      )}
      {showOlder && olderGroups.map((group, gi) => <ToolCallGroupView key={`o-${gi}`} group={group} defaultExpanded={false} />)}
      {recentGroups.map((group, gi) => <ToolCallGroupView key={`r-${gi}`} group={group} defaultExpanded />)}
      {toolCalls.length > 0 && (
        <div className="px-2 text-[10px] text-text-muted">
          🔧 {totalDone}/{toolCalls.length} 完成{totalRunning > 0 ? ` · ${totalRunning} 运行中` : ''}
        </div>
      )}
    </div>
  );
}

export function ToolCallsCollapsed({ toolCalls }: { toolCalls: ToolCallInfo[] }) {
  const grouped = useMemo(() => groupToolCalls(toolCalls), [toolCalls]);
  const errors = toolCalls.filter(tc => tc.is_error).length;
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-2 border-t border-border/50 pt-2">
      <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-1.5 px-2 py-1 text-[11px] text-text-muted hover:text-text-secondary select-none w-full">
        <span>🔧 工具调用 ×{toolCalls.length}</span>
        {errors > 0 && <span className="text-status-error">({errors} 失败)</span>}
        <span className="ml-auto text-[10px]">{expanded ? '收起' : '展开'}</span>
      </button>
      {expanded && (
        <div className="mt-1 space-y-1">
          {grouped.map((group, gi) => <ToolCallGroupView key={`c-${gi}`} group={group} defaultExpanded={false} />)}
        </div>
      )}
    </div>
  );
}

export function ToolCallsStreamingStatus({ toolCalls, isStreaming }: { toolCalls: ToolCallInfo[]; isStreaming: boolean }) {
  if (!isStreaming || toolCalls.length === 0 || !toolCalls.every(tc => tc.status === 'done')) return null;
  return (
    <div className="mt-2 flex items-center gap-2 text-[11px] text-text-muted">
      <Loader2 size={12} className="animate-spin text-accent" />
      <span>正在整理结果并生成回复...</span>
    </div>
  );
}
